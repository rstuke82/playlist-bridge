import {useEffect,useState} from 'react'
export type MBSettings={enabled:boolean;cache_days:number;release_priority:string[];prefer_studio:boolean;retries:number;cache_entries:number}
export async function mbCall<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000)
 try{const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});const data=await r.json();if(!r.ok){const e=Object.assign(new Error(typeof data.detail==='string'?data.detail:'MusicBrainz request failed.'),{status:r.status,retryable:r.status===429||r.status===504||(r.status===502&&/HTTP 503|HTTP 429|Connection failed/.test(data.detail||''))});throw e}return data}finally{clearTimeout(timer)}
}
export async function mbLookup<T>(body:unknown,retries:number,onStatus:(message:string)=>void,active:()=>boolean):Promise<T>{
 for(let attempt=0;;attempt++){
  if(!active())throw new Error('Lookup cancelled')
  onStatus(`Searching MusicBrainz · attempt ${attempt+1} of ${retries+1}…`)
  try{return await mbCall<T>('/api/lidarr/search','POST',body)}catch(e:any){
   if(!e.retryable||attempt>=retries)throw e
   for(let seconds=15*(attempt+1);seconds>0;seconds--){if(!active())throw new Error('Lookup cancelled');onStatus(`MusicBrainz is busy or unavailable. Retrying in ${seconds}s · attempt ${attempt+2} of ${retries+1}`);await new Promise(resolve=>setTimeout(resolve,1000))}
  }
 }
}
export default function MusicBrainzSettings(){
 const [value,setValue]=useState<MBSettings|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('')
 useEffect(()=>{let active=true;mbCall<MBSettings>('/api/settings/musicbrainz').then(v=>{if(active)setValue(v)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[])
 async function action(fn:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await fn()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 function move(index:number,delta:number){if(!value)return;const order=[...value.release_priority];[order[index],order[index+delta]]=[order[index+delta],order[index]];setValue({...value,release_priority:order})}
 return <section className="panel settings-panel"><h2>MusicBrainz</h2><p className="muted">Find albums for missing tracks. No API key is required.</p>{!value&&!error&&<p>Loading settings…</p>}{value&&<fieldset className="lidarr-fields" disabled={busy}>
 <label className="playlist-choice"><input type="checkbox" checked={value.enabled} onChange={e=>setValue({...value,enabled:e.target.checked})}/> Enable MusicBrainz lookups</label>
 <h3>Release priority</h3><p className="muted">Applies to both Lidarr and MusicBrainz album results. Every candidate remains available for review.</p>
 {value.release_priority.map((type,i)=><div className="alias-row" key={type}><span>{i+1}. {type}</span><div><button aria-label={`Move ${type} up`} disabled={i===0} onClick={()=>move(i,-1)}>↑</button> <button aria-label={`Move ${type} down`} disabled={i===3} onClick={()=>move(i,1)}>↓</button></div></div>)}
 <label className="playlist-choice"><input type="checkbox" checked={value.prefer_studio} onChange={e=>setValue({...value,prefer_studio:e.target.checked})}/> Prefer studio releases over live, compilation and remix releases</label><p className="muted">This uses MusicBrainz labels; missing labels cannot guarantee a studio recording.</p>
 <h3>Lookups and cache</h3><div className="form-grid"><label>Automatic retries<select value={value.retries} onChange={e=>setValue({...value,retries:Number(e.target.value)})}>{[0,1,2,3].map(n=><option key={n} value={n}>{n===0?'Off':`${n} retries`}</option>)}</select></label><label>Keep cached results<select value={value.cache_days} onChange={e=>setValue({...value,cache_days:Number(e.target.value)})}><option value={7}>7 days</option><option value={30}>30 days</option></select></label></div>
 <p className="muted">Retries wait 15, 30, then 45 seconds. Retry Once always makes one attempt, without automatic retries. {value.cache_entries} cached lookups.</p>
 <div className="actions"><button onClick={()=>action(async()=>{setMessage('Testing MusicBrainz · one request…');const r=await mbCall<{message:string}>('/api/settings/musicbrainz/test','POST');setMessage(r.message)})}>Test Connection</button><button onClick={()=>action(async()=>{const r=await mbCall<MBSettings>('/api/settings/musicbrainz/cache','DELETE');setValue(v=>v?{...v,cache_entries:r.cache_entries}:v);setMessage('Metadata cache cleared.')})}>Clear Cache</button></div>
 <div className="settings-save"><button className="primary" onClick={()=>action(async()=>{setValue(await mbCall<MBSettings>('/api/settings/musicbrainz','PUT',value));setMessage('MusicBrainz settings saved.')})}>Save Changes</button></div>
 </fieldset>}{message&&<p role="status">{message}</p>}{error&&<p role="alert" className="error">{error}</p>}</section>
}
