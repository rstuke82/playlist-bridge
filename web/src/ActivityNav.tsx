import { useEffect, useState } from 'react'
import { Job, activeJob } from './api'
import { Icon } from './Controls'
import { actionName } from './Activity'
export default function ActivityNav({jobs,page,mobile=false}:{jobs:Job[];page:string;mobile?:boolean}){
 const [seen,setSeen]=useState(()=>{try{return localStorage.getItem('bridge-activity-reviewed')||''}catch{return ''}})
 const active=jobs.find(j=>j.status==='running')||jobs.find(activeJob)
 const latestFailure=jobs.filter(j=>['failed','interrupted'].includes(j.status)&&j.finished_at).sort((a,b)=>(b.finished_at||'').localeCompare(a.finished_at||''))[0]
 const attention=!!latestFailure&&(latestFailure.finished_at||'')>seen
 useEffect(()=>{if(page==='activity'&&latestFailure?.finished_at){setSeen(latestFailure.finished_at);try{localStorage.setItem('bridge-activity-reviewed',latestFailure.finished_at)}catch{}}},[page,latestFailure?.finished_at])
 const lanes=Object.values(active?.activity?.lanes||{}) as any[]
 const lane=lanes.find(l=>!['completed','failed'].includes(l.mode)&&l.playlist_index)
 const label=active?(active.status==='queued'?'Job queued':lane?.mode==='waiting'?`Waiting for ${lane.service}`:lane?.playlist_index?`${active.action==='sync'?'Syncing':actionName(active.action)} ${lane.playlist_index} of ${lane.playlist_total}`:actionName(active.action)):attention?'Needs attention':'No active jobs'
 return <button className={`activity-nav ${page==='activity'?'active':''} ${attention&&!active?'needs-attention':''}`} onClick={()=>{location.hash='activity'}} title={label} aria-label={`Activity: ${label}`}><span className="activity-nav-icon"><Icon name="activity"/>{(active||attention)&&<i className={active?'activity-dot':'attention-dot'}/>}</span><span>Activity{!mobile&&<small>{label}</small>}</span></button>
}
