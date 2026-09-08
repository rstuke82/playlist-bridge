import { useEffect, useState } from 'react'
import { api, Job, activeJob } from './api'
import { stamp } from './HealthCard'
export const actionName=(value:string)=>({sync:'Sync',health:'Check health',analyze:'Analyze playlist',add:'Add playlist',fix_match:'Fix match',ignore:'Ignore track',startup:'Startup',jobs:'Job system'}[value]||value)
export default function JobsPanel({jobs,refresh}:{jobs:Job[];refresh:()=>Promise<void>}){
  const [schedules,setSchedules]=useState<any[]>([])
  const [error,setError]=useState('')
  const [action,setAction]=useState('sync'),[scope,setScope]=useState('automatic')
  const [editing,setEditing]=useState<string|undefined>()
  const blank=()=>({name:'',action:'sync',scope:'automatic',cron:'0 3 * * *',timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC',enabled:true})
  const [form,setForm]=useState(blank)
  async function load(){setSchedules(await api.schedules())}
  useEffect(()=>{load().catch(e=>setError(e.message));const id=setInterval(()=>{load().catch(()=>{})},5000);return()=>clearInterval(id)},[])
  async function run(fn:()=>Promise<any>){setError('');try{await fn();await load();await refresh()}catch(e:any){setError(e.message)}}
  return <>
    <section className="panel"><h2>Jobs & schedules</h2><p className="muted">Jobs run in the background, one at a time. You can leave this page. Cancellation stops at a safe checkpoint; an active playlist update may finish first. Completed changes are retained.</p>{error&&<p role="alert" className="error">{error}</p>}
      <div className="toolbar"><label>Action<select value={action} onChange={e=>setAction(e.target.value)}><option value="sync">Sync</option><option value="health">Check health</option></select></label><label>Scope<Scope value={scope} change={setScope}/></label><button onClick={()=>run(()=>api.enqueue(action,{scope}))}>Run now</button></div>
      <h3>{editing?'Edit schedule':'New schedule'}</h3><form onSubmit={e=>{e.preventDefault();run(async()=>{await api.saveSchedule(form,editing);setEditing(undefined);setForm(blank())})}}>
        <div className="form-grid"><label>Name<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Action<select value={form.action} onChange={e=>setForm({...form,action:e.target.value})}><option value="sync">Sync</option><option value="health">Check health</option></select></label><label>Scope<Scope value={form.scope} change={scope=>setForm({...form,scope})}/></label><label>Cron expression<input required value={form.cron} onChange={e=>setForm({...form,cron:e.target.value})}/></label><label>Timezone<input required value={form.timezone} onChange={e=>setForm({...form,timezone:e.target.value})}/></label></div>
        <p className="muted">Five fields: minute hour day month weekday. “0 3 * * *” runs daily at 03:00 in the timezone above. Missed runs are coalesced; a schedule does not overlap itself.</p><label><input type="checkbox" checked={form.enabled} onChange={e=>setForm({...form,enabled:e.target.checked})}/> Enabled</label> <button className="primary">Save schedule</button>{editing&&<button type="button" onClick={()=>{setEditing(undefined);setForm(blank())}}>Cancel edit</button>}
      </form>
      {schedules.map(s=><div className="manage-row" key={s.id}><h3>{s.name}</h3><p>{actionName(s.action)} · {s.scope} · {s.cron} · {s.timezone}<br/>{s.enabled?`Next run: ${stamp(s.next_run)}`:'Paused'}</p><div className="actions"><button onClick={()=>run(()=>api.runSchedule(s.id))}>Run now</button><button onClick={()=>{setEditing(s.id);setForm({...s,enabled:!!s.enabled})}}>Edit</button><button onClick={()=>run(()=>api.saveSchedule({...s,enabled:!s.enabled},s.id))}>{s.enabled?'Pause':'Enable'}</button><button onClick={()=>run(()=>api.deleteSchedule(s.id))}>Delete schedule</button></div></div>)}
    </section>
    <section className="panel"><h2>Job history</h2><p className="muted">Latest 200 jobs. Interrupted jobs are not replayed automatically after a server restart.</p>{jobs.map(job=><JobRow key={job.id} job={job} refresh={refresh}/>)}{!jobs.length&&<p>No jobs yet.</p>}</section>
  </>
}
export function Scope({value,change}:{value:string;change:(s:string)=>void}){return <select value={value} onChange={e=>change(e.target.value)}><option value="all">All playlists</option><option value="favorites">Favorites</option><option value="automatic">Automatic playlists</option></select>}
export function JobRow({job,refresh}:{job:Job;refresh:()=>Promise<void>}){
  const [error,setError]=useState('')
  return <article className="job-row"><div className="panel-head"><strong>{actionName(job.action)} · {job.status}</strong>{activeJob(job)&&<button disabled={job.status==='cancelling'} onClick={async()=>{try{await api.cancel(job.id);await refresh()}catch(e:any){setError(e.message)}}}>{job.status==='cancelling'?'Cancelling…':'Cancel job'}</button>}</div>
    <p role={activeJob(job)?'status':undefined}>{activeJob(job)&&<span className="spinner"/>}{job.progress}</p><small>{stamp(job.created_at)} · {job.payload.scope||job.payload.url||'Selected track/playlist'}</small>
    {(job.error||error)&&<p className="error">{job.error||error}</p>}
    {job.result?.playlists&&<details><summary>Playlist results ({job.result.playlists.length})</summary>{job.result.playlists.map((p:any)=><p key={p.key}><a href={`#playlist/${encodeURIComponent(p.key)}`}>{p.name||p.key}</a> · {p.ok?'Completed':p.error}</p>)}</details>}
    {job.action==='analyze'&&job.result&&<p>{job.result.name}: {job.result.source_tracks} source tracks, {job.result.matched} matched, {job.result.unresolved} unresolved.</p>}
    {job.action==='add'&&job.result?.key&&<p>Added <a href={`#playlist/${encodeURIComponent(job.result.key)}`}>{job.result.name}</a></p>}
    {job.action==='fix_match'&&job.result&&<p>{job.result.affected} occurrences fixed; {job.result.synced_playlists} playlists synced.</p>}
  </article>
}
