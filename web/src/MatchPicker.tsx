import { useEffect, useRef, useState } from 'react'
import { api, Candidate, MissingTrack, Playlist } from './api'
import Modal from './Modal'

export default function MatchPicker({track,playlistKey,onClose,onSave}:{
  track: Pick<MissingTrack,'title'|'artist'|'album'>; playlistKey?:string;
  onClose:()=>void; onSave:(candidate:Candidate,keys?:string[],provenance?:string)=>Promise<void>
}) {
  const [candidates,setCandidates]=useState<Candidate[]>([])
  const [automatic,setAutomatic]=useState<Candidate|null>(null),[automaticDone,setAutomaticDone]=useState(false)
  const [provenance,setProvenance]=useState('manual')
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
    let active=true
    api.playlists().then(p=>{if(active)setPlaylists(p)}).catch(()=>{})
    retryAutomatic()
    return ()=>{active=false;generation.current++}
  },[])
  async function retryAutomatic(){
    const id=++generation.current
    setLoading(true)
    try{
      const result=await api.automatic(track)
      if(id!==generation.current)return
      setAutomatic(result.candidate);setAutomaticDone(true)
      if(result.candidate){setChoice(result.candidate);setProvenance('automatic');setCandidates([])}else{await search('')}
    }catch(e:any){if(id===generation.current){setError(e.message);setAutomaticDone(true)}}
    finally{if(id===generation.current)setLoading(false)}
  }
  async function search(text:string){
    const id=++generation.current
    setLoading(true);setError('');setChoice(null);setProvenance('manual')
    try{const rows=await api.candidates({...track,query:text});if(id===generation.current)setCandidates(rows)}
    catch(e:any){if(id===generation.current){setError(e.message);setCandidates([])}}
    finally{if(id===generation.current)setLoading(false)}
  }
  async function save(){
    if(!choice||savingRef.current)return
    savingRef.current=true;setSaving(true);setError('')
    try{await onSave(choice,all?undefined:keys,provenance);onClose()}
    catch(e:any){setError(e.message)}
    finally{savingRef.current=false;setSaving(false)}
  }
  return <Modal onClose={onClose} busy={saving}>
    <div className="modal match-dialog" role="dialog" aria-modal="true" aria-labelledby="match-title" ref={dialog} onClick={e=>e.stopPropagation()}>
      <div className="modal-header"><h2 id="match-title">Choose a match</h2><button disabled={saving} onClick={onClose} aria-label="Close match picker">✕ Close</button></div>
      <div className="modal-body">
        <h3>{track.title}</h3><p>{track.artist} · {track.album||'N/A'}</p>
        <p className="muted">Select a candidate, then Save Match to queue the update. Cancel leaves the current match unchanged.</p>
        <label><input type="checkbox" checked={all} disabled={saving} onChange={e=>setAll(e.target.checked)}/> Apply to all matching missing occurrences</label>
        {!all&&playlists.map(p=><label className="playlist-choice" key={p.key}><input type="checkbox" disabled={saving||p.key===playlistKey} checked={keys.includes(p.key)} onChange={e=>setKeys(e.target.checked?[...keys,p.key]:keys.filter(k=>k!==p.key))}/>{p.name}{p.key===playlistKey?' (current playlist)':''}</label>)}
        {playlistKey&&<p className="muted">The current playlist's match will also be replaced. Only affected playlists sync.</p>}
        {automaticDone&&<section className="automatic-candidate"><h3>Auto match retry</h3>{automatic?<><p><strong>{automatic.title}</strong> — {automatic.artist} · {automatic.album}</p><p>The current automatic matcher selected this candidate. Accepting this suggestion records Auto provenance.</p><button disabled={saving} onClick={()=>{setChoice(automatic);setProvenance('automatic')}}>Use Match</button></>:<p>No strong automatic candidate was found.</p>}<button disabled={loading||saving} onClick={()=>search('')}>Show More Candidates</button><button disabled={saving} onClick={()=>dialog.current?.querySelector<HTMLInputElement>('input[aria-label="Search Plex"]')?.focus()}>Manual Search</button></section>}
        <form className="add" onSubmit={e=>{e.preventDefault();search(query)}}><input aria-label="Search Plex" placeholder="Search Plex title, artist or album" value={query} disabled={saving} onChange={e=>setQuery(e.target.value)}/><button disabled={saving||loading}>Search</button></form>
        {error&&<p role="alert" className="error">{error}</p>}
        {loading?<p role="status"><span className="spinner"/> Retrying automatic matching / finding candidates… You can cancel while this runs.</p>:<>
          {!candidates.length&&!automatic&&<p>No candidates found. Try another search.</p>}
          {candidates.map(c=><button type="button" className={`candidate ${choice?.plex_id===c.plex_id?'chosen':''}`} aria-pressed={choice?.plex_id===c.plex_id} disabled={saving} key={c.plex_id} onClick={()=>{setChoice(c);setProvenance('manual')}}><span><strong>{c.title}</strong><small>{c.artist} · {c.album||'N/A'}</small></span><b>{c.score}%</b></button>)}
        </>}
      </div>
      <div className="modal-footer"><button disabled={saving} onClick={onClose}>Cancel</button><span role="status">{saving?'Queuing match update…':choice?`Selected: ${choice.title}`:'No changes saved'}</span><button className="primary" disabled={saving||loading||!choice||(!all&&!keys.length)} onClick={save}>{saving?'Queuing…':`Save ${provenance==='automatic'?'Auto':'Manual'} Match`}</button></div>
    </div>
  </Modal>
}
