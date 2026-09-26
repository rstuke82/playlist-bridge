import {useState} from 'react'
import {request} from './api'
export default function ImportUsers({done}:{done:()=>void}){
 const [rows,setRows]=useState<any[]|null>(null),[selected,setSelected]=useState<string[]>([]),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 async function run(fn:()=>Promise<void>){setBusy(true);setMessage('');try{await fn()}catch(e:any){setMessage(e.message)}finally{setBusy(false)}}
 return <section><button disabled={busy} onClick={()=>run(async()=>{setRows(await request<any[]>('/api/users/import'));setSelected([])})}>Import Plex Users</button>{rows&&<><p>Select accounts with access to the music library. Each person still signs in through Plex.</p>{rows.map(u=><label key={u.id}><input type="checkbox" disabled={busy||u.existing} checked={selected.includes(u.id)} onChange={e=>setSelected(e.target.checked?[...selected,u.id]:selected.filter(id=>id!==u.id))}/>{u.name}{u.existing?' · Already imported':''}</label>)}<button disabled={busy||!selected.length} onClick={()=>run(async()=>{const result=await request<any>('/api/users/import',{method:'POST',body:JSON.stringify({ids:selected})});setMessage(`${result.imported} users imported`);setRows(null);done()})}>Import Selected</button></>}{message&&<p role="status">{message}</p>}</section>
}
