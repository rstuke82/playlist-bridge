import { useEffect, useState } from 'react'
import { api, Job } from './api'
import { showActivity } from './Activity'
export default function MatchQueue({jobs}:{jobs:Job[]}){
 const [data,setData]=useState<any>({rows:[],playlist_count:0}),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const revision=jobs.filter(j=>j.action==='match_batch').map(j=>`${j.id}:${j.status}`).join('|')
 useEffect(()=>{let active=true;const load=()=>api.matchQueue().then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError(e.message)});void load();window.addEventListener('jobs-refresh',load);return()=>{active=false;window.removeEventListener('jobs-refresh',load)}},[revision])
 if(!data.rows.length&&!error)return null
 return <section className="panel match-queue"><div className="panel-head"><div><h2>Match queue · {data.rows.length} edits</h2><p className="muted">Saved for review. Apply together to sync each of {data.playlist_count} affected playlists once.</p></div><button className="primary" disabled={busy||!data.rows.length} onClick={async()=>{setBusy(true);setError('');try{const job=await api.applyMatchQueue();setData(await api.matchQueue());showActivity(job.id)}catch(e:any){setError(e.message)}finally{setBusy(false)}}}>Apply Matches & Sync</button></div><details><summary>Review queued edits</summary>{data.rows.map((r:any)=><div className="queued-match" key={r.id}><span><strong>{r.source.title}</strong> — {r.source.artist}<small>{r.playlist_name} · {r.provenance==='automatic'?'Auto':'Manual'} → {r.candidate?.title||`Plex track ${r.plex_id}`}</small></span><button disabled={busy} onClick={async()=>{setBusy(true);try{await api.discardMatch(r.id);setData(await api.matchQueue())}catch(e:any){setError(e.message)}finally{setBusy(false)}}}>Discard</button></div>)}</details>{error&&<p className="error" role="alert">{error}</p>}</section>
}
