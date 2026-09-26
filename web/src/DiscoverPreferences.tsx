import {useEffect,useState} from 'react'
import {request} from './api'
export function DiscoverPreferences(){
 const [value,setValue]=useState<any>(null),[message,setMessage]=useState('')
 useEffect(()=>{request('/api/discover/preferences').then(setValue).catch(e=>setMessage(e.message))},[])
 return <section className="panel"><h2>Last.fm</h2><p>Save your username to explore your listening history. The server supplies the API connection.</p>{value&&<form onSubmit={async e=>{e.preventDefault();try{await request('/api/discover/preferences',{method:'PUT',body:JSON.stringify(value)});setMessage('Saved')}catch(e:any){setMessage(e.message)}}}><label>Last.fm username<input value={value.lastfm_username} onChange={e=>setValue({...value,lastfm_username:e.target.value})}/></label><button>Save</button></form>}<p role="status">{message}</p></section>
}
export function BlockedArtists(){
 const [rows,setRows]=useState<any[]>([]),[name,setName]=useState(''),[error,setError]=useState('')
 const load=()=>request<any[]>('/api/discover/blocked-artists').then(setRows).catch(e=>setError(e.message))
 useEffect(()=>{void load()},[])
 return <section className="panel"><h2>Blocked Artists</h2><p>These artists are excluded from your Discover results.</p><form className="add" onSubmit={async e=>{e.preventDefault();try{await request('/api/discover/blocked-artists',{method:'POST',body:JSON.stringify({name})});setName('');await load()}catch(e:any){setError(e.message)}}}><input aria-label="Artist name" placeholder="Artist name" required value={name} onChange={e=>setName(e.target.value)}/><button>Block Artist</button></form>{rows.map(r=><div className="panel-head" key={r.id}><span>{r.name}</span><button onClick={async()=>{try{await request('/api/discover/blocked-artists/'+r.id,{method:'DELETE'});await load()}catch(e:any){setError(e.message)}}}>Unblock</button></div>)}{error&&<p role="alert">{error}</p>}</section>
}
