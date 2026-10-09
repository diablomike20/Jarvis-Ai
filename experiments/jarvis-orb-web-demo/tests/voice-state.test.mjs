import test from 'node:test';
import assert from 'node:assert/strict';
import {JARVIS_STATES,ORB_MOODS,normalizeState,normalizeAudioLevel,resolveOrbVisual,localBridgeCommand} from '../src/voice-state.mjs';
test('all JARVIS states have orb moods',()=>{for(const state of JARVIS_STATES)assert.ok(ORB_MOODS[state]);});
test('aliases and invalid states normalize',()=>{assert.equal(normalizeState(' responding '),'SPEAKING');assert.equal(normalizeState('active'),'LISTENING');assert.equal(normalizeState('X'),'IDLE');});
test('bounded, finite audio',()=>{assert.equal(normalizeAudioLevel(-3),0);assert.equal(normalizeAudioLevel(3),1);assert.equal(normalizeAudioLevel(Infinity),0);});
test('voice intensity only in speaking/listening',()=>{assert.equal(resolveOrbVisual('IDLE',1).voiceLevel,0);assert.equal(resolveOrbVisual('SPEAKING',0.7).voiceLevel,0.7);});
test('unknown messages are rejected',()=>{assert.equal(localBridgeCommand({type:'eval',code:'x'}),null);assert.deepEqual(localBridgeCommand({type:'jarvis-state',state:'LISTENING'}),{type:'state',value:'LISTENING'});});
test('orb custom-state targets are finite',()=>{for(const m of Object.values(ORB_MOODS)){if(typeof m==='string')continue;for(const n of Object.values(m))assert.ok(Number.isFinite(n)&&n>=0&&n<=2);}});
