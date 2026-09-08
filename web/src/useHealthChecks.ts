import { useRef, useState } from 'react'
import { api, Playlist, PlaylistHealth } from './api'

export function useHealthChecks(refresh:()=>Promise<void>) {
  const [checking,setChecking]=useState<Record<string,boolean>>({})
  const [results,setResults]=useState<Record<string,PlaylistHealth>>({})
  const [errors,setErrors]=useState<Record<string,string>>({})
  const [status,setStatus]=useState('')
  const [batch,setBatch]=useState(false)
  const active=useRef(new Set<string>())
  const batchActive=useRef(false)
  async function perform(p:Playlist){
    if(active.current.has(p.key))return false
    active.current.add(p.key)
    setChecking(v=>({...v,[p.key]:true}));setErrors(v=>({...v,[p.key]:''}))
    try{
      const result=await api.playlistHealth(p.key)
      setResults(v=>({...v,[p.key]:result}))
      await refresh()
      return true
    }catch(e:any){
      setErrors(v=>({...v,[p.key]:e.message}))
      await refresh().catch(()=>{})
      return false
    }finally{active.current.delete(p.key);setChecking(v=>({...v,[p.key]:false}))}
  }
  async function checkOne(p:Playlist){
    if(batchActive.current||active.current.has(p.key))return
    setStatus(`Checking health: ${p.name}…`)
    const ok=await perform(p)
    setStatus(ok?`Health check complete: ${p.name}`:`Health check failed: ${p.name}. See the error below or Settings → Logs.`)
  }
  async function checkAll(playlists:Playlist[]){
    if(batchActive.current||active.current.size||!playlists.length)return
    batchActive.current=true;setBatch(true)
    let failed=0
    try{
      for(let i=0;i<playlists.length;i++){
        setStatus(`Checking playlist ${i+1} of ${playlists.length}: ${playlists[i].name}…`)
        if(!await perform(playlists[i]))failed++
      }
      setStatus(`Health checks finished: ${playlists.length-failed} completed, ${failed} failed.`)
    }finally{batchActive.current=false;setBatch(false)}
  }
  return {checking,results,errors,status,batch,checkOne,checkAll,running:batch||Object.values(checking).some(Boolean)}
}
export type HealthChecks = ReturnType<typeof useHealthChecks>
