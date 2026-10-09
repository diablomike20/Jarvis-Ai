import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
const output=path.resolve('perf-results');await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1});
const errors=[];page.on('pageerror',error=>errors.push(String(error.message).slice(0,300)));
try{
 await page.goto(process.env.ORB_BASE_URL||'http://127.0.0.1:5173',{waitUntil:'networkidle',timeout:60000});
 await page.waitForSelector('[data-testid="current-state"]');
 const checks=[];
 for(const state of ['IDLE','LISTENING','THINKING','SPEAKING','SUCCESS','ERROR']){
  await page.getByTestId('state-'+state.toLowerCase()).click();await page.waitForTimeout(650);
  const display=await page.getByTestId('current-state').textContent();checks.push({state,display,pass:state===display});
 }
 await page.evaluate(()=>{window.setBrahmaState('SPEAKING');window.setAudioLevel(0.77);});
 await page.waitForTimeout(700);
 const bridge={state:await page.getByTestId('current-state').textContent(),audio:await page.getByTestId('audio-level-value').textContent()};
 await page.getByTestId('state-listening').click();
 await page.screenshot({path:path.join(output,'orb-listening.png'),fullPage:true});
 const browserPerf=await page.evaluate(()=>({
   canvasCount:document.querySelectorAll('[data-testid="orb-stage"] canvas').length,
   dimensions:[...document.querySelectorAll('[data-testid="orb-stage"] canvas')].map(c=>({width:c.width,height:c.height})),
   webgl2:!!document.createElement('canvas').getContext('webgl2'),
   userAgent:navigator.userAgent
 }));
 let legacy=null;
 if(process.env.ORB_LEGACY_URL){
  const lp=await browser.newPage({viewport:{width:1440,height:960}}),oldErrors=[];
  lp.on('pageerror',e=>oldErrors.push(String(e.message).slice(0,260)));
  try{
   await lp.goto(process.env.ORB_LEGACY_URL,{waitUntil:'load',timeout:60000});
   await lp.waitForTimeout(3000);
   legacy={canvasCount:await lp.locator('canvas').count(),pageErrors:oldErrors,mode:'headless Chromium, NOT Qt WebEngine'};
   await lp.screenshot({path:path.join(output,'original-background.png')});
  }catch(e){legacy={error:String(e).slice(0,350),pageErrors:oldErrors};}
  finally{await lp.close();}
 }
 const result={package:'jarvis-ai-web-animation@0.1.2',stateChecks:checks,bridge,browserPerf,legacy,
   uiRafFps:await page.getByTestId('fps').textContent(),uiFrameP95:await page.getByTestId('p95').textContent(),
   pageErrors:errors,note:'requestAnimationFrame is UI cadence, not actual Three.js frame count or GPU timer'};
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
 if(checks.some(c=>!c.pass)||bridge.state!=='SPEAKING'||bridge.audio!=='77%'||errors.length)process.exitCode=1;
}finally{await browser.close();}
