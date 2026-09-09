import { useEffect, useRef, useState } from 'react'
import { api, Job, activeJob } from './api'
import { stamp } from './HealthCard'

export const actionName=(value:string)=>({sync:'Sync',health:'Health Check',analyze:'Analyze playlist',add:'Add playlist',fix_match:'Fix Match',ignore:'Ignore track',startup:'Startup',jobs:'Jobs'}[value]||value)
export function showActivity(id:string){window.dispatchEvent(new CustomEvent('show-activity',{detail:id}))}
const duration=(seconds:number)=>seconds<60?`${seconds}s`:`${Math.floor(seconds/60)}m ${seconds%60}s`
const elapsed=(value?:string,end=Date.now())=>value?duration(Math.max(0,Math.floor((end-Date.parse(value))/1000))):'0s'
type EventRow={id?:number;created_at:string;stage?:string;message:string}

export function Terminal({events,copy,empty='Waiting for output…'}:{events:EventRow[];copy?:()=>Promise<string>;empty?:string}){
 const viewport=useRef<HTMLDivElement>(null)
 const [follow,setFollow]=useState(true),[copied,setCopied]=useState(''),[fallback,setFallback]=useState('')
 const [copying,setCopying]=useState(false)
 useEffect(()=>{if(follow&&viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight},[events,follow])
 async function copyLog(){setCopying(true);try{const text=copy?await copy():events.map(e=>`${stamp(e.created_at)}  ${e.message}`).join('\n');if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(text);setCopied('Copied')}else{setFallback(text);setCopied('Select the log below to copy')}}catch(e:any){setCopied(e.message)}finally{setCopying(false)}}
 return <div className="terminal-shell"><div className="terminal-tools"><span>Live output{events.length>=1000?' · latest 1,000 lines':''}</span><div className="actions"><button className="small-button" aria-pressed={follow} onClick={()=>setFollow(v=>!v)}>{follow?'Following output':'Follow output ↓'}</button><button className="small-button" disabled={copying} onClick={copyLog}>{copying?'Preparing…':'Copy log'}</button></div></div>
 <div className="terminal-output" ref={viewport} tabIndex={0} aria-label="Operation output" onScroll={()=>{const el=viewport.current;if(el&&el.scrollHeight-el.scrollTop-el.clientHeight>40)setFollow(false)}}>{events.length?events.slice(-1000).map((e,i)=><div className={`terminal-line ${/✗|failed|error/i.test(e.message)?'line-error':/LOST|unresolved|unmatched|⚠/i.test(e.message)?'line-warning':/✓|complete/i.test(e.message)?'line-success':''}`} key={e.id||i}><time title={stamp(e.created_at)}>{new Date(e.created_at).toLocaleTimeString()}</time><span>{e.message}</span></div>):<p className="muted">{empty}</p>}</div>
 {copied&&<p className="copy-status" role="status">{copied}</p>}{fallback&&<textarea className="copy-fallback" aria-label="Log text to copy" readOnly value={fallback} onFocus={e=>e.target.select()}/>}</div>
}

export function OperationOutput({stage,loading,error}:{stage:any;loading:boolean;error:string}){
 const [time,setTime]=useState(Date.now()),[hidden,setHidden]=useState(false)
 useEffect(()=>{if(loading){setHidden(false);const timer=setInterval(()=>setTime(Date.now()),1000);return()=>clearInterval(timer)}},[loading])
 if(hidden||(!loading&&!stage.events.length))return null
 const last=stage.events.at(-1),match=last?.message.match(/Comparing tracks (\d+) \/ (\d+)/)
 return <section className="operation-output"><div className="panel-head"><strong>{loading?'Loading playlist':error?'Could not load playlist':'Playlist ready'}</strong>{!loading&&<button className="small-button" onClick={()=>setHidden(true)}>Dismiss output</button>}</div><p role="status">{error||last?.message||'Starting…'}{loading&&last&&` · ${elapsed(last.created_at,time)} in this stage`}</p>{loading&&match&&<progress value={Number(match[1])} max={Number(match[2])}/>}
 <Terminal events={stage.events} empty="Starting playlist request…"/></section>
}

function ResultSummary({job}:{job:Job}){
 const results=job.result?.playlists
 const batch=Array.isArray(results)
 const total=job.result?.total??job.activity?.playlist_total
 const successful=batch?results.filter((r:any)=>r.ok===true||(r.ok==null&&r.summary&&!r.summary.errors)).length:0
 const failed=batch?results.filter((r:any)=>r.ok===false).length:0
 const running=activeJob(job)
 const lanes=Object.values(job.activity?.lanes||{}) as any[]
 const started=lanes.filter(l=>l.key!=='job'&&l.playlist_index).length
 const notStarted=total!=null?Math.max(0,total-Math.max(started,results?.length||0)):null
 const records=batch?results.filter((r:any)=>r.ok!==false).map((r:any)=>r.result?.health||r.result?.summary||r.result||r.summary):[job.result?.health||job.result]
 const sum=(keys:string[])=>{let known=false;const n=records.reduce((n:number,r:any)=>{const key=keys.find(k=>typeof r?.[k]==='number');if(!key)return n;known=true;return n+r[key]},0);return known?n:null}
 const counts=[['Matched',sum(['matched_in_library','matched'])],['Missing',sum(['unresolved'])],['LOST',sum(['lost','newly_lost'])]]
 return <div className="result-summary">{batch&&<p>{successful} playlists completed · {failed} failed{notStarted!==null?` · ${notStarted} not started`:''}{!running&&results.length<Number(total)&&started>results.length?' · remaining started work was stopped':''}</p>}<div className="result-counts">{counts.filter(([,v])=>v!==null).map(([label,value])=><span key={label}>{value} <small>{label}</small></span>)}</div>{job.error&&<p className="error" role="alert">{job.error}</p>}{!running&&job.status==='cancelled'&&<p>Stopped at a safe checkpoint. Completed changes were kept; review the output for any unfinished playlist.</p>}{job.result?.key&&<a href={`#playlist/${encodeURIComponent(job.result.key)}`}>Open {job.result.name||'playlist'}</a>}</div>
}

export default function Activity({jobs}:{jobs:Job[]}){
 const [id,setId]=useState(()=>{try{return sessionStorage.getItem('bridge-activity')||''}catch{return ''}})
 const [open,setOpen]=useState(true),[detail,setDetail]=useState<Job|null>(null),[events,setEvents]=useState<EventRow[]>([]),[error,setError]=useState(''),[clock,setClock]=useState(Date.now())
 const cursor=useRef(0),shown=useRef(new Set<string>()),scrollNext=useRef(false),panel=useRef<HTMLElement>(null)
 const listed=jobs.find(j=>j.id===id)
 // Expanded state comes from the same response as its event stream.
 const job=detail?.id===id?detail:listed
 useEffect(()=>{function show(e:Event){const key=(e as CustomEvent<string>).detail;shown.current.add(key);setId(key);setOpen(true);scrollNext.current=true}window.addEventListener('show-activity',show);return()=>window.removeEventListener('show-activity',show)},[])
 useEffect(()=>{const active=jobs.find(j=>j.status==='running')||jobs.find(activeJob);if(active&&!shown.current.has(active.id)){shown.current.add(active.id);setId(active.id);setOpen(true)}},[jobs])
 useEffect(()=>{try{if(id)sessionStorage.setItem('bridge-activity',id);else sessionStorage.removeItem('bridge-activity')}catch{}},[id])
 useEffect(()=>{cursor.current=0;setEvents([]);setDetail(null);setError('')},[id])
 useEffect(()=>{if(scrollNext.current&&open){panel.current?.scrollIntoView({behavior:'smooth',block:'start'});scrollNext.current=false}},[id,open,job])
 useEffect(()=>{
   if(!id||!open)return
   let alive=true,timer:ReturnType<typeof setTimeout>|undefined,terminalReads=0
   async function poll(){
     try{
       const response=await api.live(id,cursor.current)
       if(!alive)return
       setDetail(response.job);setError('')
       if(response.events.length){cursor.current=response.events.at(-1).id;setEvents(old=>[...old,...response.events].slice(-1000))}
       terminalReads=activeJob(response.job)?0:terminalReads+1
       if(activeJob(response.job)||response.events.length===1000||terminalReads<2)timer=setTimeout(poll,response.events.length===1000?50:1000)
       if(!activeJob(response.job))window.dispatchEvent(new Event('jobs-refresh'))
     }catch(e:any){if(alive){setError(e.message);timer=setTimeout(poll,10000)}}
   }
   void poll()
   return()=>{alive=false;if(timer)clearTimeout(timer)}
 },[id,open])
 useEffect(()=>{if(!open&&listed)setDetail(listed)},[listed,open])
 useEffect(()=>{if(!job||!activeJob(job))return;const timer=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(timer)},[job?.id,job?.status])
 if(!id)return null
 if(!job)return <section className="panel"><p>{error||'Opening activity…'}</p><button onClick={()=>setId('')}>Dismiss</button></section>
 const active=activeJob(job)
 const lanes=(Object.values(job.activity?.lanes||{}) as any[]).filter(l=>!['completed','failed'].includes(l.mode))
 const current=lanes.filter(l=>l.key!=='job').length?lanes.filter(l=>l.key!=='job'):lanes
 const target=current[0]?.name||job.payload.url||job.payload.title||({all:'All playlists',favorites:'Favorites',automatic:'Auto Sync playlists'}[job.payload.scope as string])||job.payload.playlist_keys?.join(', ')||'Playlist operation'
 const stage=active&&current[0]?.mode==='waiting'?`Waiting for ${current[0].service}`:job.progress
 async function cancel(){try{await api.cancel(id);window.dispatchEvent(new Event('jobs-refresh'))}catch(e:any){setError(e.message)}}
 return <section className={`activity-panel ${open?'is-open':'is-collapsed'}`} ref={panel} aria-label="Current activity"><div className="activity-bar"><button className="activity-toggle" aria-expanded={open} onClick={()=>setOpen(v=>!v)}><span className={`activity-light ${job.status}`} aria-hidden="true"/><span><strong>{actionName(job.action)} · {active?target:job.status}</strong><small>{stage} · {elapsed(job.started_at,active?clock:Date.parse(job.finished_at||job.started_at||''))}</small></span><span aria-hidden="true">{open?'⌃':'⌄'}</span></button>{!active&&<button className="small-button" onClick={()=>{setId('');setDetail(null)}}>Dismiss</button>}</div>
 {open&&<div className="activity-body"><div className="panel-head"><h2>{actionName(job.action)} <small className="muted">{job.status}</small></h2>{active&&<button disabled={job.status==='cancelling'} onClick={cancel}>{job.status==='cancelling'?'Stopping…':'Stop job'}</button>}</div>
 <small className="muted">Started {stamp(job.started_at)}{job.finished_at&&` · Finished ${stamp(job.finished_at)}`}</small>
 {active&&current.map(l=><div className="activity-stage" key={l.key}><strong>{l.name}{l.playlist_index&&l.playlist_total?` · playlist ${l.playlist_index} of ${l.playlist_total}`:''}</strong><p role="status">{l.mode==='waiting'?`Waiting for ${l.service} · ${elapsed(l.since,clock)}`:l.stage}</p>{l.mode==='waiting'&&<small className="muted">{l.stage} · request pending</small>}{l.total>0&&l.completed!=null&&<progress max={l.total} value={l.completed}/>}</div>)}
 {job.status==='queued'&&<p>Queued — waiting for the current job to finish.</p>}{job.status==='cancelling'&&<p>Stopping at the next safe checkpoint. If a Plex update has begun, that playlist update finishes first. Completed changes are kept.</p>}
 <ResultSummary job={job}/>{error&&<p className="error" role="alert">{error}</p>}
 <Terminal events={events} copy={()=>api.jobLog(id)} empty={active?'Waiting for the worker’s first output…':'No detailed events in this older job. Saved results are available below.'}/>
 {!active&&<a className="download-log" href={`/api/jobs/${id}/log`} download>Download full log</a>}
 {job.result?.playlists&&<details><summary>Playlist results</summary>{job.result.playlists.map((r:any)=><p key={r.key}><a href={`#playlist/${encodeURIComponent(r.key)}`}>{r.name||r.key}</a> · {r.ok===false?r.error:'Completed'}</p>)}</details>}
 </div>}</section>
}
