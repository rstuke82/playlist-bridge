import { useEffect, useMemo, useState } from 'react'
import { api, Candidate, MissingTrack, Playlist } from './api'

type Page = 'dashboard' | 'playlists' | 'missing'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [health, setHealth] = useState<any>(null)
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [missing, setMissing] = useState<MissingTrack[]>([])
  const [scope, setScope] = useState<'all' | 'favorites'>('all')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [h, p, m] = await Promise.all([api.health(), api.playlists(), api.missing(scope)])
    setHealth(h); setPlaylists(p); setMissing(m)
  }
  useEffect(() => { refresh().catch(e => setMessage(e.message)) }, [scope])

  async function run(label: string, action: () => Promise<any>) {
    setBusy(true); setMessage(`${label}…`)
    try { await action(); setMessage(`${label} complete`); await refresh() }
    catch (e: any) { setMessage(e.message) }
    finally { setBusy(false) }
  }

  return <div className="shell">
    <aside>
      <div className="brand">Playlist Bridge <span>2.0 beta</span></div>
      <nav>
        {(['dashboard','playlists','missing'] as Page[]).map(p =>
          <button className={page===p?'active':''} onClick={()=>setPage(p)} key={p}>{p[0].toUpperCase()+p.slice(1)}</button>
        )}
      </nav>
    </aside>
    <main>
      <header><div><h1>{page[0].toUpperCase()+page.slice(1)}</h1><p>{message || 'Spotify / Apple Music → Plex'}</p></div>
        <div className="actions"><button disabled={busy} onClick={()=>run('Sync favorites', api.syncFavorites)}>Sync Favorites</button><button className="primary" disabled={busy} onClick={()=>run('Sync all', api.syncAll)}>Sync All</button></div>
      </header>
      {page==='dashboard' && <Dashboard health={health} playlists={playlists} />}
      {page==='playlists' && <Playlists playlists={playlists} refresh={refresh} run={run} />}
      {page==='missing' && <Missing tracks={missing} scope={scope} setScope={setScope} refresh={refresh} />}
    </main>
  </div>
}

function Dashboard({health, playlists}:{health:any, playlists:Playlist[]}) {
  const last = useMemo(() => playlists.filter(p=>p.last_synced).sort((a,b)=>String(b.last_synced).localeCompare(String(a.last_synced)))[0], [playlists])
  return <>
    <section className="cards">
      <Stat label="Playlists" value={health?.playlists ?? '—'} />
      <Stat label="Favorites" value={health?.favorites ?? '—'} />
      <Stat label="Unresolved" value={health?.unresolved ?? '—'} warn />
      <Stat label="LOST" value={health?.lost ?? '—'} danger />
    </section>
    <section className="panel"><h2>Playlist health</h2>
      <div className="rows">{playlists.map(p=><PlaylistRow playlist={p} key={p.key} />)}</div>
      {!playlists.length && <p>No playlists registered yet.</p>}
    </section>
    <section className="panel"><h2>Last sync</h2><p>{last ? `${last.name} — ${new Date(last.last_synced!).toLocaleString()}` : 'No sync history yet.'}</p></section>
  </>
}

function Stat({label,value,warn,danger}:{label:string,value:any,warn?:boolean,danger?:boolean}) {
  return <div className={`stat ${warn?'warn':''} ${danger?'danger':''}`}><span>{label}</span><strong>{value}</strong></div>
}

function PlaylistRow({playlist}:{playlist:Playlist}) {
  return <div className="playlist-row"><span className="star">{playlist.favorite?'★':'☆'}</span><div className="grow"><strong>{playlist.name}</strong><small>{playlist.source} · {playlist.saved_matches} matched · {playlist.unresolved} unresolved</small></div><span className={playlist.auto_sync?'pill on':'pill off'}>{playlist.auto_sync?'AUTO ON':'AUTO OFF'}</span></div>
}

function Playlists({playlists,refresh,run}:{playlists:Playlist[],refresh:()=>Promise<void>,run:(l:string,a:()=>Promise<any>)=>Promise<void>}) {
  const [url,setUrl]=useState(''); const [analysis,setAnalysis]=useState<any>(null); const [favorite,setFavorite]=useState(false); const [autoSync,setAutoSync]=useState(true); const [error,setError]=useState('')
  async function analyze(){setError('');setAnalysis(null);try{setAnalysis(await api.analyzePlaylist(url))}catch(e:any){setError(e.message)}}
  async function add(){try{await api.addPlaylist({url,favorite,auto_sync:autoSync});setUrl('');setAnalysis(null);await refresh()}catch(e:any){setError(e.message)}}
  return <>
    <section className="panel"><h2>Add playlist</h2><div className="add"><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="Paste Spotify or Apple Music playlist URL"/><button onClick={analyze}>Analyze</button></div>
      {error&&<p className="error">{error}</p>}
      {analysis&&<div className="analysis"><div><strong>{analysis.name}</strong><p>{analysis.source_tracks} source · {analysis.matched} matched · {analysis.unresolved} unresolved</p></div><label><input type="checkbox" checked={favorite} onChange={e=>setFavorite(e.target.checked)}/> Favorite</label><label><input type="checkbox" checked={autoSync} onChange={e=>setAutoSync(e.target.checked)}/> Auto Sync</label><button className="primary" onClick={add}>Add Playlist</button></div>}
    </section>
    <section className="panel"><h2>Registered playlists</h2>{playlists.map(p=><div className="manage-row" key={p.key}><PlaylistRow playlist={p}/><div className="row-actions"><button onClick={()=>run(`Sync ${p.name}`,()=>api.syncOne(p.key))}>Sync</button><button onClick={async()=>{await api.updatePlaylist(p.key,{favorite:!p.favorite});await refresh()}}>{p.favorite?'Unfavorite':'Favorite'}</button><button onClick={async()=>{await api.updatePlaylist(p.key,{auto_sync:!p.auto_sync});await refresh()}}>{p.auto_sync?'Disable Auto':'Enable Auto'}</button></div></div>)}</section>
  </>
}

function Missing({tracks,scope,setScope,refresh}:{tracks:MissingTrack[],scope:'all'|'favorites',setScope:(s:'all'|'favorites')=>void,refresh:()=>Promise<void>}) {
  const [selected,setSelected]=useState<MissingTrack|null>(null); const [candidates,setCandidates]=useState<Candidate[]>([]); const [error,setError]=useState('')
  async function review(track:MissingTrack){setSelected(track);setError('');try{setCandidates(await api.candidates(track))}catch(e:any){setError(e.message)}}
  async function choose(c:Candidate){if(!selected)return;try{const r=await api.saveMatch(selected,c.plex_id);setSelected(null);setCandidates([]);setError(`Saved across ${r.affected} occurrence(s)`);await refresh()}catch(e:any){setError(e.message)}}
  return <section className="panel"><div className="panel-head"><h2>Missing tracks</h2><div><button className={scope==='all'?'active-tab':''} onClick={()=>setScope('all')}>All</button><button className={scope==='favorites'?'active-tab':''} onClick={()=>setScope('favorites')}>★ Favorites</button></div></div>{error&&<p className="error">{error}</p>}
    <div className="rows">{tracks.map((t,i)=><div className="missing-row" key={`${t.artist}-${t.title}-${i}`}><div className="grow"><strong>{t.title}</strong><small>{t.artist} {t.album?`· ${t.album}`:''} · {t.occurrence_count} occurrence(s) / {t.playlist_count} playlist(s)</small></div>{t.lost_occurrence_count?<span className="pill lost">LOST {t.lost_occurrence_count}</span>:null}<button onClick={()=>review(t)}>Review Match</button></div>)}</div>
    {selected&&<div className="modal-backdrop" onClick={()=>setSelected(null)}><div className="modal" onClick={e=>e.stopPropagation()}><h2>{selected.title}</h2><p>{selected.artist} · {selected.album||'N/A'}</p><h3>Plex candidates</h3>{candidates.map(c=><button className="candidate" key={c.plex_id} onClick={()=>choose(c)}><span><strong>{c.title}</strong><small>{c.artist} · {c.album||'N/A'}</small></span><b>{c.score}%</b></button>)}<button onClick={()=>setSelected(null)}>Cancel</button></div></div>}
  </section>
}
