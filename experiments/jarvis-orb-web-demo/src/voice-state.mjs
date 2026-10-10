/** Read-only state/volume adapter for JARVIS; no microphone, XTTS or WebSocket. */
export const JARVIS_STATES=Object.freeze(['IDLE','LISTENING','THINKING','SPEAKING','SUCCESS','ERROR','OFFLINE']);
export const ORB_MOODS=Object.freeze({
  IDLE:'idle',
  LISTENING:Object.freeze({energy:1.24,rotationSpeed:0.8,particleSpeed:1.22,shellRadius:1.07,ringSpread:1.02,filamentOpacity:0.63,coreScale:1.1,bloom:0.91}),
  THINKING:'thinking',
  SPEAKING:Object.freeze({energy:1.18,rotationSpeed:0.92,particleSpeed:1.18,shellRadius:1.09,ringSpread:1.07,filamentOpacity:0.62,coreScale:1.10,bloom:0.96}),
  SUCCESS:'success', ERROR:'alert',
  OFFLINE:Object.freeze({energy:0.35,rotationSpeed:0.18,particleSpeed:0.2,shellRadius:0.88,ringSpread:0.80,filamentOpacity:0.2,coreScale:0.72,bloom:0.19})
});
export function normalizeState(input){
 const value=String(input??'').trim().toUpperCase();
 const aliases={ACTIVE:'LISTENING',WAKE:'LISTENING',LISTEN:'LISTENING',PROCESSING:'THINKING',RESPONDING:'SPEAKING',TALKING:'SPEAKING',ALERT:'ERROR',FAILED:'ERROR',SLEEPING:'IDLE'};
 const state=aliases[value]||value; return JARVIS_STATES.includes(state)?state:'IDLE';
}
export function normalizeAudioLevel(input){const n=Number(input);return Number.isFinite(n)?Math.min(1,Math.max(0,n)):0;}
export function resolveOrbVisual(state,audioLevel=0){
 const selected=normalizeState(state), audio=normalizeAudioLevel(audioLevel);
 const voiceLevel=['LISTENING','SPEAKING'].includes(selected)?audio:0;
 return {state:selected,mood:ORB_MOODS[selected],intensity:Math.min(1.55,0.75+voiceLevel*0.8),voiceLevel};
}
export function localBridgeCommand(event){
 if(!event||typeof event!=='object')return null;
 if(event.type==='jarvis-state'&&typeof event.state==='string')return {type:'state',value:normalizeState(event.state)};
 if(event.type==='jarvis-audio'&&typeof event.level==='number')return {type:'audio',value:normalizeAudioLevel(event.level)};
 return null;
}
