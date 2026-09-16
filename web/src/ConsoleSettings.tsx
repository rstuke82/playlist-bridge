import { useEffect, useState } from 'react'
import { api } from './api'
export default function ConsoleSettings(){
 const [debug,setDebug]=useState(false),[loaded,setLoaded]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 useEffect(()=>{api.consoleSettings().then(s=>{setDebug(s.debug);setLoaded(true)}).catch(e=>setMessage(e.message))},[])
 return <section className="panel settings-panel"><h2>Console logging</h2><label className="playlist-choice"><input type="checkbox" checked={debug} disabled={!loaded||busy} onChange={async e=>{const next=e.target.checked;setBusy(true);try{await api.saveConsole(next);setDebug(next);setMessage('Console logging updated.')}catch(e:any){setMessage(e.message)}finally{setBusy(false)}}}/> Enable debug output in the server console</label><p className="muted">Off by default. Enable detailed matching output and successful request logs when troubleshooting. Errors and job summaries remain visible. Activity keeps its detailed logs in either mode.</p>{message&&<p role="status">{message}</p>}</section>
}
