import { useEffect, useMemo, useState } from 'react'
import { api, Candidate, MissingTrack, Playlist, PlaylistHealth, PlexLibrary } from './api'

type Page = 'dashboard' | 'playlists' | 'missing' | 'settings'

export default function App() {
  const [detailKey, setDetailKey] = useState<string>(() => decodeURIComponent(location.hash.slice(1)))
  useEffect(() => { const change = () => setDetailKey(decodeURIComponent(location.hash.slice(1))); window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change) }, [])
  const [page, setPage] = useState<Page>('dashboard')
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
          <button className={page===p?'active':''} onClick={()=>{location.hash='';setPage(p)}} key={p}>{p[0].toUpperCase()+p.slice(1)}</button>
        )}
      </nav>
      <div className="sidebar-bottom">
        <button className={!detailKey && page==='settings'?'active':''} onClick={()=>{location.hash='';setPage('settings')}}>Settings</button>
        <div className="sidebar-version">
          <span>{health?.version || '2.0.0-beta.1'}</span>
          <small>Build {health?.build || '20260908.6'}</small>
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
      {!detailKey && page==='dashboard' && <Dashboard health={health} playlists={playlists} refresh={refresh} onToggleFavorite={toggleFavorite} setMessage={setMessage} />}
      {!detailKey && page==='playlists' && <Playlists playlists={playlists} refresh={refresh} run={run} onToggleFavorite={toggleFavorite} />}
      {!detailKey && page==='missing' && <Missing tracks={missing} scope={scope} setScope={setScope} refresh={refresh} />}
      {!detailKey && page==='settings' && <Settings setMessage={setMessage} refresh={refresh} />}
      {detailKey && <PlaylistDetail playlistKey={detailKey} refresh={refresh}/>}
    </main>
  </div>
}

function Dashboard({health, playlists, refresh, onToggleFavorite, setMessage}:{health:any, playlists:Playlist[], refresh:()=>Promise<void>, onToggleFavorite:(p:Playlist)=>Promise<void>, setMessage:(m:string)=>void}) {
  const last = useMemo(() => playlists.filter(p=>p.last_synced).sort((a,b)=>String(b.last_synced).localeCompare(String(a.last_synced)))[0], [playlists])
  const [checks, setChecks] = useState<Record<string, PlaylistHealth>>({})
  const [checking, setChecking] = useState<Record<string, boolean>>({})

  async function checkOne(playlist: Playlist) {
    setChecking(v => ({...v, [playlist.key]: true}))
    try {
      const result = await api.playlistHealth(playlist.key)
      setChecks(v => ({...v, [playlist.key]: result}))
      await refresh()
    } catch (e:any) {
      setMessage(e.message)
    } finally {
      setChecking(v => ({...v, [playlist.key]: false}))
    }
  }

  async function checkAll() {
    for (const playlist of playlists) await checkOne(playlist)
    await refresh()
  }

  return <>
    {!health?.plex_configured && <p className="muted">Plex not configured — open Settings to connect your server.</p>}
    <section className="cards">
      <Stat label="Playlists" value={health?.playlists ?? '—'} />
      <Stat label="Favorites" value={health?.favorites ?? '—'} />
      <Stat label="Unresolved" value={health?.unresolved ?? '—'} warn />
      <Stat label="LOST" value={health?.lost ?? '—'} danger />
    </section>
    <section className="panel">
      <div className="panel-head"><div><h2>Playlist health</h2><p className="muted">Read-only live check of the source playlist URL against Plex. Results are saved; Plex and sync state stay unchanged.</p></div><button disabled={Object.values(checking).some(Boolean)} onClick={checkAll}>Check All Health</button></div>
      <div className="rows">{playlists.map(p=><HealthRow playlist={p} health={checks[p.key] || p.health} checking={!!checking[p.key]} key={p.key} check={()=>checkOne(p)} toggleFavorite={()=>onToggleFavorite(p)} />)}</div>
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
    <div className="grow"><a href={`#${encodeURIComponent(playlist.key)}`}>{playlist.name}</a><small>{playlist.source} · {playlist.saved_matches} matched · {playlist.unresolved} unresolved</small></div>
    <span className={playlist.auto_sync?'pill on':'pill off'}>{playlist.auto_sync?'AUTO ON':'AUTO OFF'}</span>
  </div>
}

function HealthRow({playlist,health,checking,check,toggleFavorite}:{playlist:Playlist,health?:PlaylistHealth,checking:boolean,check:()=>void,toggleFavorite:()=>void}) {
  return <div className="health-row">
    <div className="health-top"><StarButton playlist={playlist} onClick={toggleFavorite}/><div className="grow"><a href={`#${encodeURIComponent(playlist.key)}`}>{playlist.name}</a><small>{playlist.source}</small></div>{health && <span className={health?.healthy?'pill on':'pill off'}>{health?.healthy?'HEALTHY':'DRIFT'}</span>}<button onClick={check} disabled={checking}>{checking?'Checking…':'Check Health'}</button></div>
    <details><summary>Health · Last updated: {health?.checked_at ? new Date(health?.checked_at).toLocaleString() : 'Never'}</summary><div className="health-grid">
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

function Playlists({playlists,refresh,run,onToggleFavorite}:{playlists:Playlist[],refresh:()=>Promise<void>,run:(l:string,a:()=>Promise<any>)=>Promise<void>,onToggleFavorite:(p:Playlist)=>Promise<void>}) {
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
    <section className="panel"><h2>Registered playlists</h2>{playlists.map(p=><div className="manage-row" key={p.key}><HealthRow playlist={p} health={p.health} checking={false} check={()=>run(`Check health for ${p.name}`,()=>api.playlistHealth(p.key))} toggleFavorite={()=>onToggleFavorite(p)}/><div className="row-actions"><button onClick={()=>run(`Sync ${p.name}`,()=>api.syncOne(p.key))}>Sync</button><button onClick={async()=>{await api.updatePlaylist(p.key,{auto_sync:!p.auto_sync});await refresh()}}>{p.auto_sync?'Disable Auto':'Enable Auto'}</button></div></div>)}</section>
  </>
}

function Missing({tracks,scope,setScope,refresh}:{tracks:MissingTrack[],scope:'all'|'favorites',setScope:(s:'all'|'favorites')=>void,refresh:()=>Promise<void>}) {
  const [selected,setSelected]=useState<MissingTrack|null>(null)
  const [candidates,setCandidates]=useState<Candidate[]>([])
  const [error,setError]=useState('')
  const [saving,setSaving]=useState(false)
  async function review(track:MissingTrack){setSelected(track);setError('');try{setCandidates(await api.candidates(track))}catch(e:any){setError(e.message)}}
  async function choose(c:Candidate){
    if(!selected)return
    setSaving(true)
    try{
      const r=await api.saveMatch(selected,c.plex_id)
      setSelected(null)
      setCandidates([])
      setError(`Saved across ${r.affected} occurrence(s) and synced ${r.synced_playlists} affected playlist(s)`)
      await refresh()
    }catch(e:any){setError(e.message)}
    finally{setSaving(false)}
  }
  return <section className="panel"><div className="panel-head"><h2>Missing tracks</h2><div><button className={scope==='all'?'active-tab':''} onClick={()=>setScope('all')}>All</button><button className={scope==='favorites'?'active-tab':''} onClick={()=>setScope('favorites')}>★ Favorites</button></div></div>{error&&<p className={error.startsWith('Saved')?'success':'error'}>{error}</p>}
    <div className="rows">{tracks.map((t,i)=><div className="missing-row" key={`${t.artist}-${t.title}-${i}`}><div className="grow"><strong>{t.title}</strong><small>{t.artist} {t.album?`· ${t.album}`:''} · {t.occurrence_count} occurrence(s) / {t.playlist_count} playlist(s)</small></div>{t.lost_occurrence_count?<span className="pill lost">LOST {t.lost_occurrence_count}</span>:null}<button onClick={()=>review(t)}>Review Match</button></div>)}</div>
    {selected&&<div className="modal-backdrop" onClick={()=>!saving&&setSelected(null)}><div className="modal" onClick={e=>e.stopPropagation()}><h2>{selected.title}</h2><p>{selected.artist} · {selected.album||'N/A'}</p><p className="muted">Saving a match applies it to all unresolved occurrences shown here, then syncs the affected playlists.</p><h3>Plex candidates</h3>{candidates.map(c=><button className="candidate" disabled={saving} key={c.plex_id} onClick={()=>choose(c)}><span><strong>{c.title}</strong><small>{c.artist} · {c.album||'N/A'}</small></span><b>{c.score}%</b></button>)}<button disabled={saving} onClick={()=>setSelected(null)}>{saving?'Syncing…':'Cancel'}</button></div></div>}
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

  return <section className="panel settings-panel">
    <div className="panel-head"><div><h2>Plex configuration</h2><p className="muted">Configure the Plex server used by Playlist Bridge.</p></div>{libraryName&&<span className="pill on">{libraryName}</span>}</div>
    <div className="form-grid">
      <label>Plex server URL<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="http://plex-server:32400"/></label>
      <label>Plex token<input type="password" value={token} onChange={e=>setToken(e.target.value)} placeholder={tokenHint?`Leave blank to keep ${tokenHint}`:'Enter Plex token'}/></label>
      <label>Music library<select value={libraryKey} onChange={e=>setLibraryKey(e.target.value)}><option value="">{libraryName?`${libraryName} (current)`:'Discover libraries first'}</option>{libraries.map(l=><option key={l.key} value={l.key}>{l.name}</option>)}</select></label>
    </div>
    <div className="settings-actions"><button disabled={busy||!url} onClick={discover}>Test & Discover Libraries</button><button className="primary" disabled={busy||!url||!libraryKey} onClick={save}>Save Plex Settings</button></div>
    {status&&<p className={status.startsWith('Connected')?'success':'muted'}>{status}</p>}
  </section>
}

function PlaylistDetail({playlistKey,refresh}:{playlistKey:string,refresh:()=>Promise<void>}) {
  const [data,setData]=useState<any>(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [selected,setSelected]=useState<any>(null)
  const [candidates,setCandidates]=useState<Candidate[]>([])
  const [query,setQuery]=useState('')
  const [applyAll,setApplyAll]=useState(true)
  const [selectedKeys,setSelectedKeys]=useState<string[]>([])
  const [choices,setChoices]=useState<Playlist[]>([])
  async function load(){setData(await api.detail(playlistKey))}
  useEffect(()=>{setData(null);load().catch(e=>setError(e.message))},[playlistKey])
  async function action(fn:()=>Promise<any>){setBusy(true);setError('');try{await fn();await load();await refresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
  async function review(t:any){setSelected(t);setCandidates([]);setQuery('');setSelectedKeys([playlistKey]);setApplyAll(true);try{setCandidates(await api.candidates(t));setChoices(await api.playlists())}catch(e:any){setError(e.message)}}
  return <section className="panel"><a href="#">← Back to playlists</a>{error&&<p className="error">{error}</p>}
    {!data?<p>Loading playlist…</p>:<><h2>{data.playlist.name}</h2><p>{data.playlist.source} · {data.tracks.length} tracks · Last synced: {data.playlist.last_synced ? new Date(data.playlist.last_synced).toLocaleString() : 'Never'}</p>
    <p>{data.metadata.description}</p><div className="actions"><button disabled={busy} onClick={()=>action(()=>api.syncOne(playlistKey))}>Sync Now</button></div>
    <HealthRow playlist={data.playlist} health={data.playlist.health} checking={busy} check={()=>action(()=>api.playlistHealth(playlistKey))} toggleFavorite={()=>action(()=>api.updatePlaylist(playlistKey,{favorite:!data.playlist.favorite}))}/>
    {data.tracks.map((t:any)=><div className="missing-row" key={t.index}><div className="grow"><strong>{t.index+1}. {t.title}</strong><small>{t.artist} · {t.album || 'N/A'}</small><small>Plex: {t.match ? `${t.match.title} · ${t.match.artist} · ${t.match.album || 'N/A'}` : '—'}</small></div><span className="pill">{t.status}</span><button disabled={busy || t.status==='Ignored'} onClick={()=>review(t)}>{t.plex_id?'Fix Match':'Review Match'}</button></div>)}</>}
    {selected&&<div className="modal-backdrop"><div className="modal"><h2>{selected.title}</h2><p>{selected.artist}</p><label><input type="checkbox" checked={applyAll} onChange={e=>setApplyAll(e.target.checked)}/> Apply to all matching unresolved occurrences</label>
    {!applyAll&&choices.map(p=><label key={p.key} style={{display:'block'}}><input type="checkbox" checked={selectedKeys.includes(p.key)} onChange={e=>setSelectedKeys(e.target.checked?[...selectedKeys,p.key]:selectedKeys.filter(k=>k!==p.key))}/>{p.name}</label>)}
    <p className="muted">This playlist's match will be replaced. Only affected playlists will sync.</p><div className="add"><input placeholder="Search Plex title, artist or album" value={query} onChange={e=>setQuery(e.target.value)}/><button disabled={busy} onClick={async()=>{try{setCandidates(await api.candidates({...selected,query}))}catch(e:any){setError(e.message)}}}>Search</button></div>
    {candidates.map(c=><button className="candidate" disabled={busy} key={c.plex_id} onClick={()=>action(async()=>{await api.saveMatch(selected,c.plex_id,{replace_playlist_key:playlistKey,...(applyAll?{}:{playlist_keys:selectedKeys})});setSelected(null)})}><span><strong>{c.title}</strong><small>{c.artist} · {c.album}</small></span><b>{c.score}%</b></button>)}{!candidates.length&&<p>No candidates found.</p>}<button disabled={busy} onClick={()=>setSelected(null)}>{busy?'Saving and syncing…':'Cancel'}</button></div></div>}
  </section>
}
