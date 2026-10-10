import React from 'react';
import {createRoot} from 'react-dom/client';
import {JarvisOrb,type JarvisQuality,type JarvisState} from 'jarvis-ai-web-animation';
import {JARVIS_STATES,localBridgeCommand,normalizeAudioLevel,normalizeState,resolveOrbVisual} from './voice-state.mjs';
import './style.css';

function App(){
 const [state,setState]=React.useState('IDLE'),[audio,setAudio]=React.useState(0),[simulate,setSimulate]=React.useState(false);
 const [quality,setQuality]=React.useState<JarvisQuality>('auto'),[size,setSize]=React.useState<'hero'|'panel'|'avatar'>('hero'),[paused,setPaused]=React.useState(false);
 const [fps,setFps]=React.useState(0),[p95,setP95]=React.useState(0),[jank,setJank]=React.useState(0),[webgl,setWebgl]=React.useState('waiting');
 const sequenceTimers=React.useRef<number[]>([]),visual=resolveOrbVisual(state,audio);

 React.useEffect(()=>{
  let id=0,previous=0,last=performance.now(),deltas:number[]=[];
  const tick=(now:number)=>{
   if(previous)deltas.push(now-previous);previous=now;
   if(now-last>1300){
    const sorted=[...deltas].sort((a,b)=>a-b);
    setFps(Math.round(deltas.length*1000/(now-last)));
    setP95(Number((sorted[Math.min(sorted.length-1,Math.floor(sorted.length*0.95))]||0).toFixed(1)));
    setJank(deltas.filter(n=>n>33.4).length);deltas=[];last=now;
   }
   id=requestAnimationFrame(tick);
  };
  id=requestAnimationFrame(tick);return()=>cancelAnimationFrame(id);
 },[]);
 React.useEffect(()=>{
  const id=setInterval(()=>{
    const c=document.querySelector<HTMLCanvasElement>('[data-testid="orb-stage"] canvas');
    setWebgl(c&&c.width>0&&c.height>0?'CANVAS ACTIVE':'CSS FALLBACK');
  },1000);return()=>clearInterval(id);
 },[]);
 React.useEffect(()=>{
  const handler=(event:MessageEvent)=>{
   if(event.origin!==location.origin)return;
   const command=localBridgeCommand(event.data);
   if(command?.type==='state')setState(command.value);
   if(command?.type==='audio')setAudio(command.value);
  };
  window.addEventListener('message',handler);
  const api=window as Window&{setBrahmaState?:(s:string)=>void;setAudioLevel?:(a:number)=>void;jarvisOrbDemo?:unknown};
  api.setBrahmaState=(s)=>setState(normalizeState(s));
  api.setAudioLevel=(v)=>setAudio(normalizeAudioLevel(v));
  api.jarvisOrbDemo={setState:api.setBrahmaState,setAudioLevel:api.setAudioLevel};
  return()=>{window.removeEventListener('message',handler);delete api.setBrahmaState;delete api.setAudioLevel;delete api.jarvisOrbDemo;};
 },[]);
 React.useEffect(()=>{
  if(!simulate||!['LISTENING','SPEAKING'].includes(state))return;
  let id=0;const start=performance.now();
  const tick=(now:number)=>{const t=(now-start)/1000;setAudio(normalizeAudioLevel(0.15+0.85*Math.abs(Math.sin(t*4.9)*Math.sin(t*1.6))));id=requestAnimationFrame(tick);};
  id=requestAnimationFrame(tick);return()=>cancelAnimationFrame(id);
 },[state,simulate]);
 React.useEffect(()=>()=>sequenceTimers.current.forEach(clearTimeout),[]);
 const apply=(next:string)=>{setState(normalizeState(next));if(!['SPEAKING','LISTENING'].includes(normalizeState(next)))setAudio(0);};
 const stopTimers=()=>{sequenceTimers.current.forEach(clearTimeout);sequenceTimers.current=[];};
 const choose=(next:string)=>{stopTimers();apply(next);};
 const timeline=()=>{choose('LISTENING');sequenceTimers.current=[[2300,'THINKING'],[4200,'SPEAKING'],[7200,'SUCCESS'],[8600,'IDLE']].map(([delay,s])=>window.setTimeout(()=>apply(String(s)),Number(delay)));};
 const embedded=new URLSearchParams(window.location.search).get('embed')==='1';
 return <main className={embedded?'layout embedded':'layout'}>
  <header><strong><i/> JARVIS<span>AI</span> <small>/ ORB LAB</small></strong><p>ÖNÁLLÓ TESZTPROTOTÍPUS · EREDETI ANIMÁCIÓ ÉRINTETLEN</p></header>
  <section className="columns">
   <article><div className="section-title">01 / LIVE VISUALIZATION <small>npm 0.1.2 · React + Three.js</small></div>
    <div className="stage" data-testid="orb-stage">
     <div className={'orb '+size}><JarvisOrb size={size} state={visual.mood as JarvisState} intensity={visual.intensity}
       palette="cyan" quality={quality} paused={paused} interactive draggableSpin breathing ariaLabel="JARVIS AI animated orb"/></div>
     <div className="state"><em/> <b data-testid="current-state">{state}</b> <small>VISUAL STATE</small></div>
    </div>
    <div className="metrics">
     <div><label>UI RAF FPS*</label><b data-testid="fps">{fps}</b></div>
     <div><label>P95 FRAME*</label><b data-testid="p95">{p95} ms</b></div>
     <div><label>JANK &gt;33ms*</label><b>{jank}</b></div>
     <div><label>WEBGL</label><b data-testid="webgl" className="small">{webgl}</b></div>
    </div>
    <p className="disclaimer">* requestAnimationFrame UI minta, nem a Three.js tényleges render FPS/GPU idő. CI szoftveres WebGL nem azonos a Windows célgéppel.</p>
   </article>
   <aside><div className="section-title">02 / STATE & VOICE SIMULATOR</div>
    <div className="panel"><h2>Állapotvezérlés</h2><p>Nincs mikrofon, privát hangminta vagy XTTS használat.</p>
     <div className="state-buttons">{JARVIS_STATES.map((s:string)=><button key={s} data-testid={'state-'+s.toLowerCase()} className={s===state?'active':''} onClick={()=>choose(s)}>{s}</button>)}</div>
     <button className="primary" onClick={timeline}>▶ Beszélgetési ciklus</button><hr/>
     <label htmlFor="level">Szimulált hangerő <strong data-testid="audio-level-value">{Math.round(audio*100)}%</strong></label>
     <input id="level" type="range" min="0" max="1" step="0.01" value={audio} onChange={e=>{setSimulate(false);setAudio(normalizeAudioLevel(e.target.value));}}/>
     <label className="check"><input type="checkbox" checked={simulate} onChange={e=>setSimulate(e.target.checked)}/> Automatikus hangburkoló jel</label><hr/>
     <label>Render minőség</label><select value={quality} onChange={e=>setQuality(e.target.value as JarvisQuality)}>
      {['auto','ultra','high','balanced','performance'].map(v=><option key={v}>{v}</option>)}</select>
     <label>Gömbméret</label><select value={size} onChange={e=>setSize(e.target.value as 'hero'|'panel'|'avatar')}>{['hero','panel','avatar'].map(v=><option key={v}>{v}</option>)}</select>
     <label className="check"><input type="checkbox" checked={paused} onChange={e=>setPaused(e.target.checked)}/> Render szüneteltetése</label><hr/>
     <p>Qt WebEngine kompatibilis demóvezérlés:</p><code>setBrahmaState('SPEAKING')</code><code>setAudioLevel(0.75)</code>
    </div>
   </aside>
  </section>
 </main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
