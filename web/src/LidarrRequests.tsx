import {useState,useSyncExternalStore} from 'react'
type Request={key:string;title:string;status:string;active:boolean;lidarr_id?:number;error?:string;sources:{title:string;artist:string}[]}
let rows:Request[]=[]
let inflight:Promise<void>|null=null
const listeners=new Set<()=>void>()
export function refreshLidarrRequests(){
 if(inflight)return inflight
 inflight=fetch('/api/lidarr/requests').then(async r=>{if(!r.ok)throw new Error('Could not load Lidarr request status');rows=await r.json();listeners.forEach(f=>f())}).catch(()=>{}).finally(()=>{inflight=null})
 return inflight
}
const normalize=(s:string)=>s.trim().replace(/\s+/g,' ').toLowerCase()
const labels:Record<string,string>={queued:'Queued',added:'Album added',search_pending:'Album added; search pending',search_completed:'Album added; search completed',search_failed:'Album added; search failed',search_unknown:'Album added; search submission unconfirmed',add_failed:'Request failed — inspect Lidarr'}
export function LidarrRequestStatus({track,albumKey}:{track?:{title:string;artist:string};albumKey?:string}){
 const requests=useSyncExternalStore(f=>{listeners.add(f);return()=>{listeners.delete(f)}},()=>rows)
 const [busy,setBusy]=useState(false),[error,setError]=useState('')
 const matches=requests.filter(r=>albumKey?r.key===albumKey:!!track&&r.sources.some(s=>normalize(s.title)===normalize(track.title)&&normalize(s.artist)===normalize(track.artist)))
 if(!matches.length)return null
 return <div className="lidarr-request-status">{matches.map(r=><div key={r.key}><small title={r.title}>Requested in Lidarr · {labels[r.status]||r.status}</small>{r.error&&<details><summary>Details</summary><p>{r.error}</p></details>}{!r.active&&r.lidarr_id&&['search_pending','search_failed'].includes(r.status)&&<button className="small-button" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const response=await fetch(`/api/lidarr/requests/${encodeURIComponent(r.key)}/retry-search`,{method:'POST'});if(!response.ok){const data=await response.json();throw new Error(data.detail||'Could not queue search')}await refreshLidarrRequests();window.dispatchEvent(new Event('lidarr-requested'));window.dispatchEvent(new CustomEvent('bridge-notice',{detail:'Lidarr search retry queued. The album will not be added or refreshed again.'}))}catch(e:any){setError(e.message)}finally{setBusy(false)}}}>Retry Search</button>}</div>)}{error&&<p className="error" role="alert">{error}</p>}</div>
}
