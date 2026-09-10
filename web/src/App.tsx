import { useCallback, useEffect, useRef, useState } from 'react'
import { api, Job, activeJob, Playlist, MissingTrack } from './api'
import General from './General'
import Modal from './Modal'
import QuickActions from './QuickActions'
import { playlistPredicates, openPlaylistView } from './playlistFilters'
import { matchLabel, displayText } from './labels'
import Appearance from './Appearance'
import ActivityNav from './ActivityNav'
import { About, Backups, Matching, Ignored } from './SettingsTools'
import { usePolling } from './usePolling'
import MatchPicker from './MatchPicker'
import HealthCard, { stamp, RelativeTime } from './HealthCard'
import JobsPanel, { JobRow, JobHistory, actionName } from './JobsPanel'

import Activity, { OperationOutput, showActivity } from './Activity'
import PlaylistsView from './PlaylistsView'
import SearchPage from './SearchPage'

import { Icon, FilterMenu, FilterChips, SortMenu, trackLink } from './Controls'
import TrackDetails from './TrackDetails'
import { ThemeListener, applyTheme } from './Appearance'
applyTheme()

type Enqueue=(action:string,payload?:any)=>Promise<Job>
const currentRoute=()=>{const raw=location.hash.slice(1);try{const key=decodeURIComponent(raw);if(key.startsWith('spotify:')||key.startsWith('apple:')||key.startsWith('applemusic:'))return `playlist/${encodeURIComponent(key)}`}catch{}return raw||'dashboard'}
const link=(key:string)=>`#playlist/${encodeURIComponent(key)}`
function ordered<T>(rows:T[],value:(r:T)=>any,direction:string){return [...rows].sort((a,b)=>{const x=value(a),y=value(b);if(x===null||x===undefined||x==='')return y===null||y===undefined||y===''?0:1;if(y===null||y===undefined||y==='')return -1;const n=typeof x==='number'?x-y:String(x).localeCompare(String(y),undefined,{numeric:true,sensitivity:'base'});return direction==='asc'?n:-n})}
function Direction({value,onChange}:{value:string;onChange:(s:string)=>void}){return <select aria-label="Sort direction" value={value} onChange={e=>onChange(e.target.value)}><option value="asc">Ascending</option><option value="desc">Descending</option></select>}

export default function App(){
  const [route,setRoute]=useState(currentRoute)
  useEffect(()=>{const f=()=>setRoute(currentRoute());window.addEventListener('hashchange',f);return()=>window.removeEventListener('hashchange',f)},[])
  const page=route.startsWith('playlist/')?'playlists':route.startsWith('track/')?'search':route.split('/')[0]
  let detail='';try{if(route.startsWith('playlist/'))detail=decodeURIComponent(route.slice(9))}catch{}
  let track:any=null;try{if(route.startsWith('track/')){const value=JSON.parse(decodeURIComponent(route.slice(6)));if(typeof value.title==='string'&&typeof value.artist==='string')track=value}}catch{}
  const [playlists,setPlaylists]=useState<Playlist[]>([]),[missing,setMissing]=useState<MissingTrack[]>([]),[jobs,setJobs]=useState<Job[]>([]),[health,setHealth]=useState<any>({})
  const [loaded,setLoaded]=useState({playlists:false,missing:false}),[refreshing,setRefreshing]=useState(0)
  const [message,setMessage]=useState('')
  const [revision,setRevision]=useState(0)
  const jobsRef=useRef<Job[]>([])
  const initializedJobs=useRef(false)
  const refreshPage=useCallback(async()=>{
    const reads:Promise<void>[]=[]
    setRefreshing(n=>n+1)
    if(page==='dashboard'||page==='playlists') reads.push(api.playlists().then(rows=>{setPlaylists(rows);setLoaded(v=>({...v,playlists:true}))}))
    if(page==='dashboard'||page==='missing') reads.push(api.missing().then(rows=>{setMissing(rows);setLoaded(v=>({...v,missing:true}))}))
    try{await Promise.all(reads)}finally{setRefreshing(n=>n-1)}
  },[page])
  const readJobs=useCallback(async()=>{
    const rows=await api.jobs()
    const previous=new Map(jobsRef.current.map(j=>[j.id,j]))
    if(initializedJobs.current && rows.some(j=>!activeJob(j) && (!previous.has(j.id)||activeJob(previous.get(j.id)!)))) setRevision(v=>v+1)
    // Health jobs publish each completed playlist; merge these results directly.
    const healthResults=rows.filter(j=>j.action==='health').flatMap(j=>j.result?.playlists||[]).filter(r=>r.ok&&r.result?.checked_at)
    setPlaylists(current=>current.map(p=>{
      const newest=healthResults.filter(r=>r.key===p.key).sort((a,b)=>b.result.checked_at.localeCompare(a.result.checked_at))[0]
      return newest && (!p.health?.checked_at || newest.result.checked_at>p.health.checked_at)
        ? {...p,health:newest.result,health_attempt:{attempted_at:newest.result.checked_at,error:null}} : p
    }))
    initializedJobs.current=true;jobsRef.current=rows;setJobs(rows)
  },[])
  usePolling(async()=>{try{await readJobs()}catch(e:any){setMessage(e.message)}},()=>jobsRef.current.some(activeJob)?3000:45000,'jobs-refresh')
  usePolling(async()=>{try{setHealth(await api.health())}catch(e:any){setMessage(e.message)}},()=>45000,'health-refresh')
  useEffect(()=>{refreshPage().catch(e=>setMessage(e.message))},[refreshPage,revision])
  const refresh=useCallback(async()=>{
    await Promise.all([refreshPage(),readJobs(),api.health().then(setHealth)])
  },[refreshPage,readJobs])
  const enqueue:Enqueue=async(action,payload={})=>{try{setMessage('');const job=await api.enqueue(action,payload);await readJobs();return job}catch(e:any){setMessage(e.message);throw e}}
  useEffect(()=>{if(route==='dashboard/add')document.getElementById('add-playlist')?.scrollIntoView({behavior:'smooth'})},[route])
  const active=jobs.filter(activeJob)
  const playlistCard=(label:string,filter?:string)=> <Stat key={label} label={label} value={filter?playlists.filter(playlistPredicates[filter]).length:playlists.length} onClick={()=>openPlaylistView(filter?[filter]:[])}/>
  async function favorite(p:Playlist){try{await api.updatePlaylist(p.key,{favorite:!p.favorite});await refresh()}catch(e:any){setMessage(e.message)}}
  return <div className="shell"><ThemeListener/><aside><div className="brand">Playlist Bridge</div><nav>{['dashboard','playlists','missing','search'].map(p=><button className={page===p?'active':''} key={p} onClick={()=>{location.hash=p}}><Icon name={p}/><span>{p[0].toUpperCase()+p.slice(1)}</span></button>)}</nav><div className="sidebar-bottom"><ActivityNav jobs={jobs} page={page}/><button className={page==='settings'?'active':''} onClick={()=>{location.hash='settings'}}><Icon name="settings"/><span>Settings</span></button><div className="sidebar-version">{health.release_name||'Playlist Bridge 2.0'}{health.update?.available&&<a className="update-badge" href="#settings/about" title={`Update available: ${health.update.latest_version}`}>Update available ↗</a>}</div></div></aside>
  <main><header><div><h1>{track?'Track details':detail?'Playlist details':page[0]?.toUpperCase()+page.slice(1)}</h1></div></header>
    {message&&<div className="notice"><p role="status">{message}</p><button onClick={()=>setMessage('')} aria-label="Dismiss message">×</button></div>}
    {page==='activity'&&<><Activity jobs={jobs} jobId={route.split('/')[1]||''}/><JobHistory jobs={jobs} refresh={refresh}/></>}
    {page==='search'&&!track&&<SearchPage/>}{track&&<TrackDetails key={JSON.stringify(track)} track={track} jobs={jobs} enqueue={enqueue}/>}
    {page==='dashboard'&&<><section className="cards">{playlistCard('Playlists')}{playlistCard('Favorites','Favorites')}{playlistCard('Auto Sync','Auto Sync On')}<Stat label="Missing Tracks" value={missing.length} onClick={()=>{location.hash='missing'}}/>{playlistCard('Health Drift','Health Drift')}{playlistCard('Health Errors','Health Errors')}<Stat label="Active Jobs" value={active.length} onClick={()=>{location.hash='activity'}}/>{playlistCard('Never Synced','Never Synced')}</section>{!health.plex_configured&&<p className="health-error">Plex is not configured. <a href="#settings/plex">Open Plex settings</a></p>}<QuickActions enqueue={enqueue}/><AddPlaylist jobs={jobs} enqueue={enqueue}/><section className="panel"><h2>Recent activity</h2>{jobs.slice(0,4).map(j=><JobRow key={j.id} job={j} refresh={refresh}/>)}{!jobs.length&&<p>No jobs yet.</p>}</section></>}
    {!!refreshing&&<p className="muted" role="status">Refreshing…</p>}
    {page==='playlists'&&!detail&&<PlaylistsView key={route} initialView={route.startsWith('playlists/view/')?route.slice(15):undefined} loaded={loaded.playlists} playlists={playlists} enqueue={enqueue} refresh={refresh} favorite={favorite}/>}
    {detail&&<Detail key={detail} playlistKey={detail} latest={playlists.find(p=>p.key===detail)} enqueue={enqueue} refresh={refresh} jobs={jobs}/>}
    {page==='missing'&&<Missing loaded={loaded.missing} tracks={missing} enqueue={enqueue} refresh={refresh}/>}
    {page==='settings'&&<Settings tab={route.split('/')[1]||''} jobs={jobs} refresh={refresh} setMessage={setMessage}/>}
  </main><nav className="mobile-nav" aria-label="Main navigation">{['dashboard','playlists','missing','search','activity','settings'].map(p=>p==='activity'?<ActivityNav key={p} jobs={jobs} page={page} mobile/>:<button key={p} className={page===p?'active':''} aria-current={page===p?'page':undefined} onClick={()=>{location.hash=p}}><Icon name={p}/><span>{p==='dashboard'?'Home':p[0].toUpperCase()+p.slice(1)}</span></button>)}</nav></div>

}
function Stat({label,value,onClick}:{label:string;value:number;onClick:()=>void}){return <button className="stat stat-link" onClick={onClick} aria-label={`Open ${label}: ${value}`}><span>{label}</span><strong>{value}</strong></button>}
function AddPlaylist({jobs,enqueue}:{jobs:Job[];enqueue:Enqueue}){
 const [url,setUrl]=useState(''),[favorite,setFavorite]=useState(false),[auto,setAuto]=useState(true),[id,setId]=useState(''),[error,setError]=useState(''),[pending,setPending]=useState(false)
 const job=jobs.find(j=>j.id===id),busy=pending||!!(job&&activeJob(job))
 async function add(){setPending(true);setError('');try{const j=await enqueue('add',{url:url.trim(),favorite,auto_sync:auto});setId(j.id)}catch(e:any){setError(e.message)}finally{setPending(false)}}
 return <section className="panel" id="add-playlist"><h2>Add Playlist</h2><p className="muted">Paste a public Spotify or Apple Music playlist. Playlist Bridge will match its tracks and create the Plex copy.</p><form onSubmit={e=>{e.preventDefault();void add()}}><div className="add"><input required aria-label="New playlist URL" placeholder="Spotify or Apple Music playlist URL" value={url} onChange={e=>{setUrl(e.target.value);setError('');setId('')}} disabled={busy}/><button className="primary" disabled={busy||!url.trim()}>{busy?'Adding…':'Add Playlist'}</button></div><div className="toolbar"><label><input type="checkbox" checked={favorite} onChange={e=>setFavorite(e.target.checked)} disabled={busy}/> Favorite</label><label><input type="checkbox" checked={auto} onChange={e=>setAuto(e.target.checked)} disabled={busy}/> Auto Sync</label></div></form>{error&&<p role="alert" className="error">{error}</p>}{job&&<div role="status"><p>{displayText(job.progress)}</p>{job.error&&<p className="error">{displayText(job.error)}</p>}{job.status==='completed'&&job.result?.key&&<p>Playlist added: <a href={link(job.result.key)}>{job.result.name}</a></p>}<button onClick={()=>showActivity(job.id)}>View Activity</button></div>}</section>
}
function Missing({tracks,loaded,enqueue,refresh}:{tracks:MissingTrack[];loaded:boolean;enqueue:Enqueue;refresh:()=>Promise<void>}){
 const [query,setQuery]=useState(''),[sort,setSort]=useState('occurrence_count'),[direction,setDirection]=useState('desc'),[selected,setSelected]=useState<MissingTrack|null>(null),[ignore,setIgnore]=useState<MissingTrack|null>(null),[error,setError]=useState('')
 const rows=ordered(tracks.filter(t=>`${t.title} ${t.artist} ${t.album||''}`.toLowerCase().includes(query.toLowerCase())),t=>(t as any)[sort],direction)
 return <section className="panel"><h2>Missing tracks</h2><p className="muted">An occurrence is one appearance of a track. A playlist may contain the same track twice: that is 2 occurrences in 1 playlist. Expand the counts to see where it appears.</p><div className="toolbar"><input aria-label="Filter missing tracks" placeholder="Filter by track, artist or album" value={query} onChange={e=>setQuery(e.target.value)}/><label>Sort<select value={sort} onChange={e=>setSort(e.target.value)}><option value="title">Name</option><option value="last_checked">Last checked</option><option value="occurrence_count">Occurrences</option><option value="playlist_count">Playlist count</option></select></label><Direction value={direction} onChange={setDirection}/></div>{error&&<p role="status">{error}</p>}
 {rows.map((t,i)=><article className="playlist-card" key={`${t.title}-${t.artist}`}><div className="panel-head"><div><a className="track-title" href={trackLink(t)}>{t.title}</a><p>{t.artist} · {t.album||'N/A'}</p></div><div className="actions"><button onClick={()=>setSelected(t)}>Review Match</button><button onClick={()=>setIgnore(t)}>Ignore</button></div></div><small>Last checked by sync/match: {stamp(t.last_checked)}</small><details><summary>{t.occurrence_count} occurrences in {t.playlist_count} playlists</summary>{t.memberships.map(m=><p key={m.key}><a href={link(m.key)}>{m.name}</a> · {m.count} occurrence(s)</p>)}</details></article>)}{!loaded?<p role="status">Loading missing tracks…</p>:!rows.length&&<div className="empty-state"><p>{query?'No missing tracks match your filter.':'No missing tracks. You’re all caught up.'}</p>{query&&<button onClick={()=>setQuery('')}>Clear Filter</button>}</div>}
 {selected&&<MatchPicker track={selected} onClose={()=>setSelected(null)} onSave={async(c,keys,provenance)=>{await enqueue('fix_match',{title:selected.title,artist:selected.artist,album:selected.album||'',plex_id:c.plex_id,provenance,playlist_keys:keys});setError('')}}/>}
 {ignore&&<IgnoreDialog track={ignore} close={()=>setIgnore(null)} done={async()=>{await refresh();setError('Ignore saved. Plex changes apply on the next sync.')}}/>}
 </section>
}
function IgnoreDialog({track,close,done}:{track:MissingTrack;close:()=>void;done:()=>Promise<void>}){
 const [universal,setUniversal]=useState(false),[keys,setKeys]=useState(track.memberships.map(m=>m.key)),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 return <Modal onClose={close} busy={busy}><div className="modal" role="dialog" aria-modal="true" aria-label="Ignore track"><h2>Ignore {track.title}</h2><p>{track.artist}</p><label><input type="checkbox" checked={universal} onChange={e=>setUniversal(e.target.checked)}/> Ignore universally — all current and future playlists</label>{!universal&&track.memberships.map(m=><label className="playlist-choice" key={m.key}><input type="checkbox" checked={keys.includes(m.key)} onChange={e=>setKeys(e.target.checked?[...keys,m.key]:keys.filter(k=>k!==m.key))}/>{m.name}</label>)}<p className="muted">Ignored tracks will be skipped by matching and removed from Plex on the next sync. Restore ignored rules in Settings → Ignored Tracks.</p>{error&&<p className="error">{error}</p>}<div className="actions"><button disabled={busy} onClick={close}>Cancel</button><button disabled={busy||(!universal&&!keys.length)} onClick={async()=>{setBusy(true);try{await api.ignore({title:track.title,artist:track.artist,album:track.album||'',universal,playlist_keys:keys});await done();close()}catch(e:any){setError(e.message)}finally{setBusy(false)}}}>Ignore track</button></div></div></Modal>
}
function Detail({playlistKey,latest,enqueue,refresh,jobs}:{playlistKey:string;latest?:Playlist;enqueue:Enqueue;refresh:()=>Promise<void>;jobs:Job[]}){
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[query,setQuery]=useState(''),[selected,setSelected]=useState<any>(null),[loading,setLoading]=useState(false)
 const [stage,setStage]=useState<any>({events:[],percent:0}),[trackFilters,setTrackFilters]=useState<string[]>([]),[trackSort,setTrackSort]=useState('order')
 const mounted=useRef(false), inflight=useRef<Promise<void>|null>(null), reload=useRef(false)
 const load=useCallback(async()=>{
   if(inflight.current){reload.current=true;return inflight.current}
   const work=(async()=>{
     do {
       reload.current=false
       if(mounted.current){setLoading(true);setError('');setStage({events:[],percent:0})}
       try{const result=await api.detail(playlistKey,p=>{if(mounted.current)setStage(p)});if(mounted.current){setData(result);setStage((previous:any)=>({...previous,events:[...previous.events,{created_at:new Date().toISOString(),message:`Playlist ready · ${result.tracks.length} source tracks`}]}))}}
       catch(e:any){if(mounted.current)setError(e.message)}
       finally{if(mounted.current)setLoading(false)}
     }while(reload.current&&mounted.current)
   })()
   inflight.current=work
   try{await work}finally{inflight.current=null}
 },[playlistKey])
 useEffect(()=>{mounted.current=true;if(!inflight.current)void load();return()=>{mounted.current=false}},[load])
 const seenJobs=useRef<Map<string,string>|null>(null)
 useEffect(()=>{
   const previous=seenJobs.current
   seenJobs.current=new Map(jobs.map(j=>[j.id,j.status]))
   if(previous && jobs.some(j=>j.status==='completed' && previous.has(j.id) && previous.get(j.id)!=='completed' && j.action!=='health' &&
      (j.payload.scope==='all'||j.payload.scope==='favorites'||j.payload.scope==='automatic'||j.payload.playlist_keys?.includes(playlistKey)||j.result?.key===playlistKey||j.result?.playlists?.some((p:any)=>p.key===playlistKey)))) void load()
 },[jobs,playlistKey,load])
 async function run(action:string){try{await enqueue(action,{scope:'selected',playlist_keys:[playlistKey]})}catch(e:any){setError(e.message)}}
 const visibleTracks=data?.tracks.filter((t:any)=>(!trackFilters.length||trackFilters.includes(matchLabel(t.status)))&&`${t.title} ${t.artist} ${t.album||''} ${t.match?.title||''}`.toLowerCase().includes(query.toLowerCase())).sort((a:any,b:any)=>trackSort==='title'?a.title.localeCompare(b.title):trackSort==='artist'?a.artist.localeCompare(b.artist):a.index-b.index)||[]
 return <section className="panel"><a href="#playlists">← Back to playlists</a>{error&&<p role="alert" className="error">{error}</p>}<OperationOutput stage={stage} loading={loading} error={error}/>{data?<><h2>{data.playlist.name}</h2><p>{data.metadata.description}</p><p>{(latest||data.playlist).favorite?'★ Favorite':'Not a favorite'} · {(latest||data.playlist).auto_sync?'Auto Sync On':'Auto Sync Off'} · <RelativeTime value={(latest||data.playlist).last_synced} prefix="Synced"/></p><div className="detail-toolbar actions"><FilterMenu choices={['Auto','Manual','Saved','LOST','Missing','Ignored']} value={trackFilters} onChange={setTrackFilters}/><SortMenu choices={{order:'Source order',title:'Track title',artist:'Artist'}} value={trackSort} onChange={setTrackSort}/><button className="icon-button" disabled={loading} title="Refresh tracks" aria-label="Refresh tracks" onClick={load}><Icon name="refresh"/></button><button className="primary" onClick={()=>run('sync')}>Sync / Refresh</button><details className="playlist-menu"><summary aria-label="More playlist actions">⋯</summary><div className="row-menu"><button onClick={()=>run('health')}>Read-only Health Check</button></div></details></div><p className="muted">{(latest||data.playlist).saved_matches} saved matches · {(latest||data.playlist).match_counts?.automatic||0} Auto · {(latest||data.playlist).match_counts?.manual||0} Manual · {(latest||data.playlist).match_counts?.legacy||0} Saved · {(latest||data.playlist).unresolved} missing · {(latest||data.playlist).lost} LOST</p><HealthCard playlist={latest||data.playlist}/><input className="track-search" placeholder="Filter tracks in this playlist" aria-label="Filter tracks in this playlist" value={query} onChange={e=>setQuery(e.target.value)}/><FilterChips value={trackFilters} onChange={setTrackFilters}/>{visibleTracks.map((t:any)=><div className="missing-row" key={t.index}><div className="grow"><strong>{t.index+1}. <a href={trackLink(t)}>{t.title}</a></strong><small>{t.artist} · {t.album||'N/A'}</small><small>Plex: {t.match?`${t.match.title} — ${t.match.artist}`:'No match'}</small></div><span className="pill">{matchLabel(t.status)}</span><button disabled={t.status==='Ignored'} onClick={()=>setSelected(t)}>{t.plex_id?'Fix Match':'Review Match'}</button></div>)}{!visibleTracks.length&&<div className="empty-state"><p>No tracks match this filter.</p><button onClick={()=>{setQuery('');setTrackFilters([])}}>Clear Filters</button></div>}</>:!loading&&<button onClick={load}>Retry loading playlist</button>}{selected&&<MatchPicker track={selected} playlistKey={playlistKey} onClose={()=>setSelected(null)} onSave={async(c,keys,provenance)=>{await enqueue('fix_match',{title:selected.title,artist:selected.artist,album:selected.album||'',plex_id:c.plex_id,provenance,playlist_keys:keys,replace_playlist_key:playlistKey});await refresh()}}/>}</section>
}
function Settings({tab,jobs,refresh,setMessage}:{tab:string;jobs:Job[];refresh:()=>Promise<void>;setMessage:(s:string)=>void}){
 const pages:Record<string,string>={general:'General',plex:'Plex',matching:'Matching',ignored:'Ignored Tracks',tasks:'Tasks',backups:'Backups',logs:'Logs',about:'About'}
 const selected=tab==='jobs'?'tasks':tab||'general'
 return <div className={`settings-layout ${tab?'settings-detail':'settings-index'}`}><nav className="settings-navigation" aria-label="Settings sections">{Object.entries(pages).map(([key,label])=><a aria-current={selected===key?'page':undefined} className={selected===key?'active-tab':''} href={`#settings/${key}`} key={key}>{label}<span>›</span></a>)}</nav><div className="settings-content"><a className="settings-back" href="#settings">← Settings</a>{selected==='general'&&<Appearance/>}{selected==='plex'&&<General refresh={refresh} setMessage={setMessage}/ >}{selected==='matching'&&<Matching/>}{selected==='ignored'&&<Ignored/>}{selected==='tasks'&&<JobsPanel jobs={jobs} refresh={refresh}/ >}{selected==='backups'&&<Backups jobs={jobs}/ >}{selected==='about'&&<About jobs={jobs}/ >}{selected==='logs'&&<Logs/>}</div></div>
}
function Logs(){
 const [entries,setEntries]=useState<any[]>([]),[level,setLevel]=useState(''),[action,setAction]=useState(''),[error,setError]=useState(''),[clear,setClear]=useState(false),[busy,setBusy]=useState(false)
 async function load(){setBusy(true);try{setEntries((await api.logs(level,action)).entries);setError('')}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 useEffect(()=>{load()},[level,action])
 return <section className="panel"><div className="panel-head"><h2>Logs</h2><div className="actions"><button disabled={busy} onClick={load}>Refresh logs</button><button onClick={()=>setClear(true)}>Clear logs</button></div></div><p className="muted">Latest 1,000 entries retained (up to 99 additional entries between cleanups); up to 200 shown. Tokens are redacted. Jobs retain their own results when logs are cleared.</p>{clear&&<Modal onClose={()=>setClear(false)} busy={busy}><div className="modal" role="dialog" aria-modal="true" aria-label="Clear application logs"><h2>Clear application logs?</h2><p>Job details and results will remain available.</p><div className="actions"> <button onClick={async()=>{try{await api.clearLogs();setClear(false);await load()}catch(e:any){setError(e.message)}}}>Confirm clear</button><button onClick={()=>setClear(false)}>Cancel</button></div></div></Modal>}<div className="toolbar"><label>Level<select value={level} onChange={e=>setLevel(e.target.value)}><option value="">All levels</option><option value="INFO">Information</option><option value="ERROR">Errors</option></select></label><label>Action<select value={action} onChange={e=>setAction(e.target.value)}><option value="">All actions</option>{['sync','health','analyze','add','fix_match','ignore','startup','jobs'].map(a=><option key={a} value={a}>{actionName(a)}</option>)}</select></label></div>{error&&<p className="error">{error}</p>}<div className="log-view">{entries.map(row=><article className="log-entry" key={row.id}><small>{stamp(row.created_at)} · {row.level} · {actionName(row.operation)}</small><pre>{displayText(row.message)}</pre></article>)}</div>{busy?<p role="status">Loading logs…</p>:!entries.length&&<p>No matching logs.</p>}</section>
}
