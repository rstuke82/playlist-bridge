import { useEffect, useRef, useState } from 'react'
import { api, Candidate, MissingTrack, Playlist } from './api'

export default function MatchPicker({track,playlistKey,onClose,onSave}:{
  track: Pick<MissingTrack,'title'|'artist'|'album'>; playlistKey?:string;
  onClose:()=>void; onSave:(candidate:Candidate,keys?:string[])=>Promise<void>
}) {
  const [candidates,setCandidates]=useState<Candidate[]>([])
  const [choice,setChoice]=useState<Candidate|null>(null)
  const [query,setQuery]=useState('')
  const [loading,setLoading]=useState(true)
  const [saving,setSaving]=useState(false)
  const [error,setError]=useState('')
  const [all,setAll]=useState(true)
  const [keys,setKeys]=useState<string[]>(playlistKey?[playlistKey]:[])
  const [playlists,setPlaylists]=useState<Playlist[]>([])
  const dialog=useRef<HTMLDivElement>(null)
  const generation=useRef(0)
  const savingRef=useRef(false)
  const closeRef=useRef(onClose)
  closeRef.current=onClose
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null
    dialog.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const keyboard=(e:KeyboardEvent)=>{
      if(e.key==='Escape'&&!savingRef.current){e.preventDefault();closeRef.current()}
      if(e.key==='Tab'){
        const items=Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]')||[])
        const first=items[0],last=items[items.length-1]
        if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}
        else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}
      }
    }
    document.addEventListener('keydown',keyboard)
    let active=true
    api.playlists().then(p=>{if(active)setPlaylists(p)}).catch(()=>{})
    search('')
    return ()=>{active=false;generation.current++;document.removeEventListener('keydown',keyboard);previous?.focus()}
  },[])
  async function search(text:string){
    const id=++generation.current
    setLoading(true);setError('');setChoice(null)
    try{const rows=await api.candidates({...track,query:text});if(id===generation.current)setCandidates(rows)}
    catch(e:any){if(id===generation.current){setError(e.message);setCandidates([])}}
    finally{if(id===generation.current)setLoading(false)}
  }
  async function save(){
    if(!choice||savingRef.current)return
    savingRef.current=true;setSaving(true);setError('')
    try{await onSave(choice,all?undefined:keys);onClose()}
    catch(e:any){setError(e.message)}
    finally{savingRef.current=false;setSaving(false)}
  }
  return <div className="modal-backdrop" onClick={()=>!saving&&onClose()}>
    <div className="modal match-dialog" role="dialog" aria-modal="true" aria-labelledby="match-title" ref={dialog} onClick={e=>e.stopPropagation()}>
      <div className="modal-header"><h2 id="match-title">Choose a match</h2><button disabled={saving} onClick={onClose} aria-label="Close match picker">✕ Close</button></div>
      <div className="modal-body">
        <h3>{track.title}</h3><p>{track.artist} · {track.album||'N/A'}</p>
        <p className="muted">Select a candidate, then Save Match. Cancel leaves the current match unchanged.</p>
        <label><input type="checkbox" checked={all} disabled={saving} onChange={e=>setAll(e.target.checked)}/> Apply to all matching unresolved occurrences</label>
        {!all&&playlists.map(p=><label className="playlist-choice" key={p.key}><input type="checkbox" disabled={saving||p.key===playlistKey} checked={keys.includes(p.key)} onChange={e=>setKeys(e.target.checked?[...keys,p.key]:keys.filter(k=>k!==p.key))}/>{p.name}{p.key===playlistKey?' (current playlist)':''}</label>)}
        {playlistKey&&<p className="muted">The current playlist's match will also be replaced. Only affected playlists sync.</p>}
        <form className="add" onSubmit={e=>{e.preventDefault();search(query)}}><input aria-label="Search Plex" placeholder="Search Plex title, artist or album" value={query} disabled={saving} onChange={e=>setQuery(e.target.value)}/><button disabled={saving||loading}>Search</button></form>
        {error&&<p role="alert" className="error">{error}</p>}
        {loading?<p role="status"><span className="spinner"/> Finding candidates… You can cancel while this runs.</p>:<>
          {!candidates.length&&<p>No candidates found. Try another search.</p>}
          {candidates.map(c=><button type="button" className={`candidate ${choice?.plex_id===c.plex_id?'chosen':''}`} aria-pressed={choice?.plex_id===c.plex_id} disabled={saving} key={c.plex_id} onClick={()=>setChoice(c)}><span><strong>{c.title}</strong><small>{c.artist} · {c.album||'N/A'}</small></span><b>{c.score}%</b></button>)}
        </>}
      </div>
      <div className="modal-footer"><button disabled={saving} onClick={onClose}>Cancel</button><span role="status">{saving?'Saving and syncing affected playlists…':choice?`Selected: ${choice.title}`:'No changes saved'}</span><button className="primary" disabled={saving||loading||!choice||(!all&&!keys.length)} onClick={save}>{saving?'Saving…':'Save Match'}</button></div>
    </div>
  </div>
}
