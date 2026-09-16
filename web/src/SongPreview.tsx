import { useState } from 'react'
import { api } from './api'
export default function SongPreview({track}:{track:{title:string;artist:string;album?:string}}){
 const [rows,setRows]=useState<any[]|null>(null),[selected,setSelected]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 return <section className="song-preview"><button disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const r=await api.applePreview(track);setRows(r.rows)}catch(e:any){setError(e.message)}finally{setBusy(false)}}}>{busy?'Finding Apple previews…':'Find Song Preview'}</button>
 {error&&<p className="error" role="status">{error}</p>}{rows&&<><p className="muted">Choose the recording you want to hear. These Apple catalog results do not change your Plex match. Preview availability varies.</p>{!rows.length&&<p>No Apple catalog previews found.</p>}{rows.map(r=><button className={`candidate ${selected?.id===r.id?'chosen':''}`} key={r.id} onClick={()=>setSelected(r)} aria-pressed={selected?.id===r.id}><span><strong>{r.title}</strong><small>{r.artist} · {r.album}</small></span><span>Preview</span></button>)}</>}
 {selected&&<><iframe key={selected.id} title={`Apple Music preview: ${selected.title}`} src={selected.embed_url} allow="encrypted-media" sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"/><p><a href={selected.store_url} target="_blank" rel="noreferrer">Open {selected.title} on Apple Music ↗</a> · <button className="small-button" onClick={()=>setSelected(null)}>Close Preview</button></p></>}
 </section>
}
