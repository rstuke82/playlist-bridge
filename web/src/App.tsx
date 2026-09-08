import { useEffect, useMemo, useState } from 'react'
import MatchPicker from './MatchPicker'
import { useHealthChecks, HealthChecks } from './useHealthChecks'
import { api, MissingTrack, Playlist, PlaylistHealth, PlexLibrary } from './api'

type Page = 'dashboard' | 'playlists' | 'missing' | 'settings'

export default function App() {
  const [route,setRoute]=useState(()=>location.hash.slice(1))
  useEffect(()=>{const change=()=>setRoute(location.hash.slice(1));window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change)},[])
  const page:Page = (['dashboard','playlists','missing','settings'].includes(route) ? route : route ? 'playlists' : 'dashboard') as Page
  let detailKey=''
  try { detailKey=route.startsWith('playlist/')?decodeURIComponent(route.slice(9)):route&&!['dashboard','playlists','missing','settings'].includes(route)?decodeURIComponent(route):'' } catch { detailKey='' }
  const [health, setHealth] = useState<any>(null)
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [missing, setMissing] = useState<MissingTrack[]>([])
  const [scope, setScope] = useState<'all' | 'favorites'>('all')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [h, p, m] = await Promise.all([api.health(), api.playlists(), api.missing(scope)])
    setHealth(h)
    setPlaylists(p)
    setMissing(m)
  }

  const checks = useHealthChecks(refresh)

  useEffect(() => { refresh().catch(e => setMessage(e.message)) }, [scope])

  async function run(label: string, action: () => Promise<any>) {
    setBusy(true)
    setMessage(`${label}…`)
    try {
      await action()
      setMessage(`${label} complete`)
      await refresh()
    } catch (e: any) {
      setMessage(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggleFavorite(playlist: Playlist) {
    try {
      await api.updatePlaylist(playlist.key, { favorite: !playlist.favorite })
      await refresh()
    } catch (e: any) {
      setMessage(e.message)
    }
  }

  const title = detailKey ? 'Playlist details' : page[0].toUpperCase() + page.slice(1)

  return <div className="shell">
    <aside>
      <div className="brand">Playlist Bridge</div>
      <nav>
        {(['dashboard','playlists','missing'] as Page[]).map(p =>
          <button className={page===p?'active':''} onClick={()=>{location.hash=p}} key={p}>{p[0].toUpperCase()+p.slice(1)}</button>
        )}
      </nav>
      <div className="sidebar-bottom">
        <button className={!detailKey && page==='settings'?'active':''} onClick={()=>{location.hash='settings'}}>Settings</button>
        <div className="sidebar-version">
          <span>{health?.version || '2.0.0-beta.2'}</span>
          <small>Build {health?.build || '20260908.7'}</small>
        </div>
      </div>
    </aside>
    <main>
      <header>
        <div><h1>{title}</h1><p>{message || 'Spotify / Apple Music → Plex'}</p></div>
        {page !== 'settings' && <div className="actions">
          <button disabled={busy} onClick={()=>run('Sync favorites', api.syncFavorites)}>Sync Favorites</button>
          <button className="primary" disabled={busy} onClick={()=>run('Sync all', api.syncAll)}>Sync All</button>
        </div>}
      </header>
      {checks.status && <div className="progress-banner" role="status" aria-live="polite">{checks.running&&<span className="spinner"/>}{checks.status}</div>}
      {!detailKey && page==='dashboard' && <Dashboard health={health} playlists={playlists} refresh={refresh} onToggleFavorite={toggleFavorite} setMessage={setMessage} checks={checks} />}
      {!detailKey && page==='playlists' && <Playlists playlists={playlists} refresh={refresh} run={run} onToggleFavorite={toggleFavorite} checks={checks} />}
      {!detailKey && page==='missing' && <Missing tracks={missing} scope={scope} setScope={setScope} refresh={refresh} />}
      {!detailKey && page==='settings' && <Settings setMessage={setMessage} refresh={refresh} />}
      {detailKey && <PlaylistDetail key={detailKey} playlistKey={detailKey} refresh={refresh} checks={checks}/>}
    </main>
  </div>
}

function Dashboard({health, playlists, onToggleFavorite, checks}:{health:any, playlists:Playlist[], refresh:()=>Promise<void>, onToggleFavorite:(p:Playlist)=>Promise<void>, setMessage:(m:string)=>void,checks:HealthChecks}) {
  const last = useMemo(() => playlists.filter(p=>p.last_synced).sort((a,b)=>String(b.last_synced).localeCompare(String(a.last_synced)))[0], [playlists])
  return <>
    {!health?.plex_configured && <p className="muted">Plex not configured — open Settings to connect your server.</p>}
    <section className="cards">
      <Stat label="Playlists" value={health?.playlists ?? '—'} />
      <Stat label="Favorites" value={health?.favorites ?? '—'} />
      <Stat label="Unresolved" value={health?.unresolved ?? '—'} warn />
      <Stat label="LOST" value={health?.lost ?? '—'} danger />
    </section>
    <section className="panel">
      <div className="panel-head"><div><h2>Playlist health</h2><p className="muted">Read-only live check of the source playlist URL against Plex. Results are saved; Plex and sync state stay unchanged.</p></div><button disabled={checks.running||!playlists.length} onClick={()=>checks.checkAll(playlists)}>Check All Health</button></div>
      <div className="rows">{playlists.map(p=><HealthRow playlist={p} health={checks.results[p.key] || p.health} checking={!!checks.checking[p.key]} error={checks.errors[p.key]} disabled={checks.running} key={p.key} check={()=>checks.checkOne(p)} toggleFavorite={()=>onToggleFavorite(p)} />)}</div>
      {!playlists.length && <p>No playlists registered yet.</p>}
    </section>
    <section className="panel"><h2>Last sync</h2><p>{last ? `${last.name} — ${new Date(last.last_synced!).toLocaleString()}` : 'No sync history yet.'}</p></section>
  </>
}

function Stat({label,value,warn,danger}:{label:string,value:any,warn?:boolean,danger?:boolean}) {
  return <div className={`stat ${warn?'warn':''} ${danger?'danger':''}`}><span>{label}</span><strong>{value}</strong></div>
}

function StarButton({playlist,onClick}:{playlist:Playlist,onClick?:()=>void}) {
  if (!onClick) return <span className={`star ${playlist.favorite?'favorite':''}`}>{playlist.favorite?'★':'☆'}</span>
  return <button className={`star-button ${playlist.favorite?'favorite':''}`} onClick={onClick} title={playlist.favorite?'Remove from favorites':'Add to favorites'} aria-label={playlist.favorite?'Remove from favorites':'Add to favorites'}>{playlist.favorite?'★':'☆'}</button>
}

function PlaylistRow({playlist,onToggleFavorite}:{playlist:Playlist,onToggleFavorite?:()=>void}) {
  return <div className="playlist-row">
    <StarButton playlist={playlist} onClick={onToggleFavorite}/>
    <div className="grow"><a href={`#playlist/${encodeURIComponent(playlist.key)}`}>{playlist.name}</a><small>{playlist.source} · {playlist.saved_matches} matched · {playlist.unresolved} unresolved</small></div>
    <span className={playlist.auto_sync?'pill on':'pill off'}>{playlist.auto_sync?'AUTO ON':'AUTO OFF'}</span>
  </div>
}

function HealthRow({playlist,health,checking,check,toggleFavorite,error,disabled}:{playlist:Playlist,health?:PlaylistHealth,checking:boolean,check:()=>void,toggleFavorite:()=>void,error?:string,disabled?:boolean}) {
  const failure = error !== undefined ? error : playlist.health_attempt?.error
  return <div className="health-row">
    <div className="health-top"><StarButton playlist={playlist} onClick={toggleFavorite}/><div className="grow"><a href={`#playlist/${encodeURIComponent(playlist.key)}`}>{playlist.name}</a><small>{playlist.source}</small></div>{health && <span className={health?.healthy?'pill on':'pill off'}>{health?.healthy?'HEALTHY':'DRIFT'}</span>}<button onClick={check} disabled={checking||disabled}>{checking?'Checking…':'Check Health'}</button></div>
    {checking&&<p className="check-status" role="status"><span className="spinner"/>Checking health… This can take a little time for large playlists.</p>}
    {!checking&&failure&&<div className="health-error" role="alert"><strong>{failure}</strong><p>{error===undefined&&playlist.health_attempt?.attempted_at&&`Last attempt: ${new Date(playlist.health_attempt.attempted_at).toLocaleString()}. `}{health?'Metrics below are from the last successful check.':'No successful health result yet.'} <a href="#settings">Open Settings</a></p></div>}
    <details><summary>Health · Last successful check: {health?.checked_at ? new Date(health?.checked_at).toLocaleString() : 'Never'}</summary><div className="health-grid">
      <HealthMetric label="Source" value={health?.source_tracks ?? '--'}/>
      <HealthMetric label="Plex playlist" value={health?.plex_playlist_tracks ?? '--'}/>
      <HealthMetric label="Matched in library" value={health?.matched_in_library ?? '--'}/>
      <HealthMetric label="Unresolved" value={health?.unresolved ?? '--'} warn={(health?.unresolved ?? 0)>0}/>
      <HealthMetric label="Ignored" value={health?.ignored ?? '--'}/>
      <HealthMetric label="Missing from Plex" value={health?.missing_from_plex_playlist ?? '--'} warn={(health?.missing_from_plex_playlist ?? 0)>0}/>
      <HealthMetric label="Extra in Plex" value={health?.extra_in_plex_playlist ?? '--'} warn={(health?.extra_in_plex_playlist ?? 0)>0}/>
      <HealthMetric label="Source + / −" value={`${health?.source_added_since_last_sync ?? '--'} / ${health?.source_removed_since_last_sync ?? '--'}`} warn={(health?.source_added_since_last_sync ?? 0)>0||(health?.source_removed_since_last_sync ?? 0)>0}/>
    </div></details>
  </div>
}

function HealthMetric({label,value,warn}:{label:string,value:any,warn?:boolean}) {
  return <div className={`health-metric ${warn?'health-warn':''}`}><span>{label}</span><strong>{value}</strong></div>
}

function Playlists({playlists,refresh,run,onToggleFavorite,checks}:{playlists:Playlist[],refresh:()=>Promise<void>,run:(l:string,a:()=>Promise<any>)=>Promise<void>,onToggleFavorite:(p:Playlist)=>Promise<void>,checks:HealthChecks}) {
  const [url,setUrl]=useState('')
  const [analysis,setAnalysis]=useState<any>(null)
  const [favorite,setFavorite]=useState(false)
  const [autoSync,setAutoSync]=useState(true)
  const [error,setError]=useState('')
  async function analyze(){setError('');setAnalysis(null);try{setAnalysis(await api.analyzePlaylist(url))}catch(e:any){setError(e.message)}}
  async function add(){try{await api.addPlaylist({url,favorite,auto_sync:autoSync});setUrl('');setAnalysis(null);await refresh()}catch(e:any){setError(e.message)}}
  return <>
    <section className="panel"><h2>Add playlist</h2><div className="add"><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="Paste Spotify or Apple Music playlist URL"/><button onClick={analyze}>Analyze</button></div>
      {error&&<p className="error">{error}</p>}
      {analysis&&<div className="analysis"><div><strong>{analysis.name}</strong><p>{analysis.source_tracks} source · {analysis.matched} matched · {analysis.unresolved} unresolved</p></div><button className={`star-button add-star ${favorite?'favorite':''}`} onClick={()=>setFavorite(!favorite)} title="Favorite this playlist">{favorite?'★':'☆'}</button><label><input type="checkbox" checked={autoSync} onChange={e=>setAutoSync(e.target.checked)}/> Auto Sync</label><button className="primary" onClick={add}>Add Playlist</button></div>}
    </section>
    <section className="panel"><h2>Registered playlists</h2>{playlists.map(p=><div className="manage-row" key={p.key}><HealthRow playlist={p} health={checks.results[p.key]||p.health} error={checks.errors[p.key]} checking={!!checks.checking[p.key]} disabled={checks.running} check={()=>checks.checkOne(p)} toggleFavorite={()=>onToggleFavorite(p)}/><div className="row-actions"><button onClick={()=>run(`Sync ${p.name}`,()=>api.syncOne(p.key))}>Sync</button><button onClick={async()=>{await api.updatePlaylist(p.key,{auto_sync:!p.auto_sync});await refresh()}}>{p.auto_sync?'Disable Auto':'Enable Auto'}</button></div></div>)}</section>
  </>
}

function Missing({tracks,scope,setScope,refresh}:{tracks:MissingTrack[],scope:'all'|'favorites',setScope:(s:'all'|'favorites')=>void,refresh:()=>Promise<void>}) {
  const [selected,setSelected]=useState<MissingTrack|null>(null)
  const [error,setError]=useState('')
  function review(track:MissingTrack){setSelected(track);setError('')}
  return <section className="panel"><div className="panel-head"><h2>Missing tracks</h2><div><button className={scope==='all'?'active-tab':''} onClick={()=>setScope('all')}>All</button><button className={scope==='favorites'?'active-tab':''} onClick={()=>setScope('favorites')}>★ Favorites</button></div></div>{error&&<p className={error.startsWith('Saved')?'success':'error'}>{error}</p>}
    <div className="rows">{tracks.map((t,i)=><div className="missing-row" key={`${t.artist}-${t.title}-${i}`}><div className="grow"><strong>{t.title}</strong><small>{t.artist} {t.album?`· ${t.album}`:''} · {t.occurrence_count} occurrence(s) / {t.playlist_count} playlist(s)</small></div>{t.lost_occurrence_count?<span className="pill lost">LOST {t.lost_occurrence_count}</span>:null}<button onClick={()=>review(t)}>Review Match</button></div>)}</div>
    {selected&&<MatchPicker track={selected} onClose={()=>setSelected(null)} onSave={async(candidate,keys)=>{
      const result=await api.saveMatch(selected,candidate.plex_id,{playlist_keys:keys})
      setError(`Saved across ${result.affected} occurrence(s) and synced ${result.synced_playlists} affected playlist(s)`)
      await refresh()
    }}/>}

  </section>
}

function Settings({setMessage,refresh}:{setMessage:(m:string)=>void,refresh:()=>Promise<void>}) {
  const [url,setUrl]=useState('')
  const [token,setToken]=useState('')
  const [tokenHint,setTokenHint]=useState('')
  const [libraries,setLibraries]=useState<PlexLibrary[]>([])
  const [libraryKey,setLibraryKey]=useState('')
  const [libraryName,setLibraryName]=useState('')
  const [busy,setBusy]=useState(false)
  const [status,setStatus]=useState('')

  useEffect(()=>{
    api.plexSettings().then(settings=>{
      setUrl(settings.url||'')
      setTokenHint(settings.token_hint||'')
      setLibraryKey(settings.music_library_key||'')
      setLibraryName(settings.music_library_name||'')
    }).catch(e=>setStatus(e.message))
  },[])

  async function discover(){
    setBusy(true); setStatus('Connecting to Plex…')
    try{
      const result=await api.discoverPlex({url,token})
      setLibraries(result.libraries)
      if (!libraryKey && result.libraries.length===1) setLibraryKey(result.libraries[0].key)
      setStatus(`Connected. Found ${result.libraries.length} music librar${result.libraries.length===1?'y':'ies'}.`)
    }catch(e:any){setStatus(e.message)}
    finally{setBusy(false)}
  }

  async function save(){
    if(!libraryKey){setStatus('Select a music library first.');return}
    setBusy(true); setStatus('Saving Plex settings…')
    try{
      const result=await api.savePlex({url,token,music_library_key:libraryKey})
      setToken('')
      setTokenHint(result.token_hint||'')
      setLibraryName(result.music_library_name||'')
      setStatus(`Connected to Plex · ${result.music_library_name}`)
      setMessage('Plex configuration saved')
      await refresh()
    }catch(e:any){setStatus(e.message)}
    finally{setBusy(false)}
  }

  return <><section className="panel settings-panel">
    <div className="panel-head"><div><h2>Plex configuration</h2><p className="muted">Configure the Plex server used by Playlist Bridge.</p></div>{libraryName&&<span className="pill on">{libraryName}</span>}</div>
    <div className="form-grid">
      <label>Plex server URL<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="http://plex-server:32400"/></label>
      <label>Plex token<input type="password" value={token} onChange={e=>setToken(e.target.value)} placeholder={tokenHint?`Leave blank to keep ${tokenHint}`:'Enter Plex token'}/></label>
      <label>Music library<select value={libraryKey} onChange={e=>setLibraryKey(e.target.value)}><option value="">{libraryName?`${libraryName} (current)`:'Discover libraries first'}</option>{libraries.map(l=><option key={l.key} value={l.key}>{l.name}</option>)}</select></label>
    </div>
    <div className="settings-actions"><button disabled={busy||!url} onClick={discover}>Test & Discover Libraries</button><button className="primary" disabled={busy||!url||!libraryKey} onClick={save}>Save Plex Settings</button></div>
    {status&&<p className={status.startsWith('Connected')?'success':'muted'}>{status}</p>}
  </section><Logs/></>
}

function PlaylistDetail({playlistKey,refresh,checks}:{playlistKey:string,refresh:()=>Promise<void>,checks:HealthChecks}) {
  const [data,setData]=useState<any>(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [selected,setSelected]=useState<any>(null)
  async function load(){setData(await api.detail(playlistKey))}
  useEffect(()=>{setData(null);load().catch(e=>setError(e.message))},[playlistKey])
  async function action(fn:()=>Promise<any>){setBusy(true);setError('');try{await fn();await load();await refresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  function review(t:any){setSelected(t);setError('')}
  return <section className="panel"><a href="#playlists">← Back to playlists</a>{error&&<p className="error">{error}</p>}
    {!data?<p>Loading playlist…</p>:<><h2>{data.playlist.name}</h2><p>{data.playlist.source} · {data.tracks.length} tracks · Last synced: {data.playlist.last_synced ? new Date(data.playlist.last_synced).toLocaleString() : 'Never'}</p>
    <p>{data.metadata.description}</p><div className="actions"><button disabled={busy} onClick={()=>action(()=>api.syncOne(playlistKey))}>Sync Now</button></div>
    <HealthRow playlist={data.playlist} health={checks.results[playlistKey]||data.playlist.health} error={checks.errors[playlistKey]} checking={!!checks.checking[playlistKey]} disabled={checks.running||busy} check={()=>checks.checkOne(data.playlist)} toggleFavorite={()=>action(()=>api.updatePlaylist(playlistKey,{favorite:!data.playlist.favorite}))}/>
    {data.tracks.map((t:any)=><div className="missing-row" key={t.index}><div className="grow"><strong>{t.index+1}. {t.title}</strong><small>{t.artist} · {t.album || 'N/A'}</small><small>Plex: {t.match ? `${t.match.title} · ${t.match.artist} · ${t.match.album || 'N/A'}` : '—'}</small></div><span className="pill">{t.status}</span><button disabled={busy || t.status==='Ignored'} onClick={()=>review(t)}>{t.plex_id?'Fix Match':'Review Match'}</button></div>)}</>}
    {selected&&<MatchPicker track={selected} playlistKey={playlistKey} onClose={()=>setSelected(null)} onSave={async(candidate,keys)=>{
      await api.saveMatch(selected,candidate.plex_id,{replace_playlist_key:playlistKey,playlist_keys:keys})
      await load();await refresh()
    }}/>}

  </section>
}

function Logs(){
  const [entries,setEntries]=useState<Awaited<ReturnType<typeof api.logs>>['entries']>([])
  const [level,setLevel]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  async function load(){setBusy(true);setError('');try{setEntries((await api.logs(level)).entries)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  useEffect(()=>{load()},[level])
  return <section className="panel"><div className="panel-head"><div><h2>Logs</h2><p className="muted">Recent web activity, health checks and sync output. The latest 1,000 entries are retained across restarts; this view shows up to 200.</p></div><button onClick={load} disabled={busy}>{busy?'Loading…':'Refresh logs'}</button></div>
    <label>Show <select aria-label="Log level" value={level} onChange={e=>setLevel(e.target.value)}><option value="">All levels</option><option value="ERROR">Errors</option><option value="INFO">Information</option></select></label>
    {error&&<p className="error" role="alert">{error}</p>}
    {!busy&&!entries.length&&<p>No log entries for this filter yet.</p>}
    <div className="log-view">{entries.map(row=><article className="log-entry" key={row.id}><small>{new Date(row.created_at).toLocaleString()} · {row.level} · {row.operation}</small><pre>{row.message}</pre></article>)}</div>
  </section>
}
