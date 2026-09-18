import {useEffect,useRef,useState,useSyncExternalStore} from 'react'
import Modal from './Modal'
type Download={queue_id:number;download_id:string;title:string;status:string;percent:number|null;remaining?:number;error?:string}
type Request={key:string;title:string;artist?:string;status:string;active:boolean;lidarr_id?:number;error?:string;sources:{title:string;artist:string}[];downloads?:Download[];download_status?:string;download_error?:string;download_poll_error?:string;download_checked_at?:number;lidarr_url?:string}
let rows:Request[]=[]
let inflight:Promise<void>|null=null
let loadError=''
let loaded=false
const listeners=new Set<()=>void>()
const notify=()=>listeners.forEach(f=>f())
export const useLidarrRequests=()=>useSyncExternalStore(f=>{listeners.add(f);return()=>{listeners.delete(f)}},()=>rows)
export function refreshLidarrRequests(){
 if(inflight)return inflight
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),90000)
 inflight=fetch('/api/lidarr/requests',{signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error('Could not load Lidarr request status');rows=await r.json();loaded=true;loadError='';notify()}).catch(e=>{loadError=e.name==='AbortError'?'Lidarr status refresh timed out':e.message;rows=[...rows];notify()}).finally(()=>{clearTimeout(timeout);inflight=null})
 return inflight
}
export function LidarrMonitor({enabled}:{enabled:boolean}){
 useEffect(()=>{if(!enabled)return;let stopped=false,timer:ReturnType<typeof setTimeout>;async function tick(){if(!document.hidden)await refreshLidarrRequests();if(!stopped)timer=setTimeout(tick,rows.some(r=>r.active||r.downloads?.length||r.download_status==='Searching')?15000:60000)}void tick();return()=>{stopped=true;clearTimeout(timer)}},[enabled]);return null
}
const normalize=(s:string)=>s.trim().replace(/\s+/g,' ').toLowerCase()
const labels:Record<string,string>={queued:'Queued',added:'Album added',search_pending:'Searching',search_completed:'Waiting for download',search_failed:'Search failed',search_unknown:'Search submission unconfirmed',add_failed:'Request failed — inspect Lidarr'}
export function LidarrRequestStatus({track,albumKey}:{track?:{title:string;artist:string};albumKey?:string}){
 const requests=useLidarrRequests()
 const matches=requests.filter(r=>albumKey?r.key===albumKey:!!track&&r.sources.some(s=>normalize(s.title)===normalize(track.title)&&normalize(s.artist)===normalize(track.artist)))
 return <div className="lidarr-request-status">{matches.map(r=><div key={r.key}><a className="small-button" href={`#activity/downloads/${encodeURIComponent(r.key)}`} title={r.title}>{r.title} · {r.download_status||labels[r.status]||r.status}{r.downloads?.[0]?.percent!=null?` · ${r.downloads[0].percent}%`:''}</a>{r.download_poll_error&&<small>Status unavailable — showing last known result</small>}</div>)}</div>
}
function DownloadCard({record:r,focused}:{record:Request;focused:boolean}){
 const [confirm,setConfirm]=useState<{action:string;download:Download}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('')
 const submitting=useRef(false),element=useRef<HTMLElement>(null)
 useEffect(()=>{if(focused)element.current?.scrollIntoView({block:'center'})},[focused])
 async function act(action:string,download?:Download){if(submitting.current)return;submitting.current=true;setBusy(true);setError('');setMessage('');try{const response=await fetch(`/api/lidarr/requests/${encodeURIComponent(r.key)}/download-action`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,queue_id:download?.queue_id,download_id:download?.download_id,confirmed:!!download})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Lidarr action failed');setConfirm(null);setMessage(data.message);await refreshLidarrRequests()}catch(e:any){setError(e.message)}finally{submitting.current=false;setBusy(false)}}
 return <article ref={element} className="panel"><h3>{r.artist?`${r.artist} — `:''}{r.title}</h3><p>{r.download_status||labels[r.status]||r.status}</p>{r.download_checked_at&&<small>Last checked: {new Date(r.download_checked_at*1000).toLocaleString()}</small>}{r.download_poll_error&&<p role="alert">Status refresh failed: {r.download_poll_error}. Showing last known information.</p>}{r.downloads?.map(d=><div key={d.queue_id} className="download-item"><strong>{d.title}</strong><p>{d.status}{d.percent!=null?` · ${d.percent}%`:''}{typeof d.remaining==='number'?` · ${(d.remaining/1024/1024).toFixed(1)} MB remaining`:''}</p>{d.percent!=null&&<progress max={100} value={d.percent} aria-label={`Download progress for ${r.title}`}/ >}{d.error&&<p className="error">{d.error}</p>}{d.download_id&&d.status!=='Imported into Lidarr'&&<div className="actions"><button disabled={busy||r.active} onClick={()=>setConfirm({action:'cancel',download:d})}>Cancel Download</button>{d.status!=='Import blocked'&&<button disabled={busy||r.active} onClick={()=>setConfirm({action:'replace',download:d})}>Find Another Download</button>}</div>}</div>)}{!r.downloads?.length&&r.error&&<p className="error">{r.error}</p>}<div className="actions">{r.lidarr_id&&!r.downloads?.length&&r.download_status!=='Imported into Lidarr'&&<button disabled={busy||r.active||r.status==='search_unknown'} onClick={()=>act('search')}>Retry Search</button>}{r.lidarr_url&&<a href={r.lidarr_url} target="_blank" rel="noreferrer">Open in Lidarr ↗</a>}</div>{message&&<p role="status">{message}</p>}{error&&!confirm&&<p role="alert" className="error">{error}</p>}{confirm&&<Modal onClose={()=>setConfirm(null)} busy={busy}><section className="modal" role="dialog" aria-modal="true" aria-label="Confirm download removal"><h2>{confirm.action==='replace'?'Find another download?':'Cancel download?'}</h2><p>{r.artist} — {r.title}</p><p>{confirm.download.title}</p><p>This removes the entire download and its downloaded files from the download client. Already imported library music and the album registration remain.</p><p>{confirm.action==='replace'?'The release will be blocklisted and Lidarr will search for a replacement.':'No immediate replacement will be requested. The album remains monitored according to its Lidarr settings and could be grabbed later.'}</p>{error&&<p className="error" role="alert">{error}</p>}<div className="actions"><button disabled={busy} onClick={()=>setConfirm(null)}>Keep Download</button><button disabled={busy} onClick={()=>act(confirm.action,confirm.download)}>{busy?'Working…':confirm.action==='replace'?'Remove & Find Another':'Cancel Download'}</button></div></section></Modal>}</article>
}
export function LidarrDownloads({albumKey=''}:{albumKey?:string}){
 const requests=useLidarrRequests()
 return <section><div className="panel-head"><h2>Album downloads</h2><button onClick={()=>void refreshLidarrRequests()}>Refresh</button></div><p className="muted">Album-level progress from Lidarr. Imported into Lidarr does not yet confirm availability in Plex.</p>{loadError&&<p role="alert" className="error">{loadError}</p>}{!loaded&&!loadError?<p role="status">Loading album requests…</p>:loaded&&!requests.length&&<p>No album requests to display.</p>}{requests.map(r=><DownloadCard key={r.key} record={r} focused={r.key===albumKey}/>)}</section>
}
