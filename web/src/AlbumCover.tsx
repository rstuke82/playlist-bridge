import {useEffect,useState,ReactNode} from 'react'
import {downloadGroup} from './requestPresentation'
export function coverStatus(row:any){
 const label=row.download_status||({approval:'Awaiting approval',queued:'Queued',added:'Album added',search_pending:'Searching',search_completed:'Waiting for download'} as Record<string,string>)[row.status]||row.availability||'Requested'
 const group=downloadGroup(row)
 if(group==='Partially Available')return {label:row.availability_detail||'Partially available in Plex',icon:'◐',tone:'partial'}
 if(group==='Needs Action'&&(row.error||row.download_error||row.downloads?.some((d:any)=>d.error)||row.removed_from_lidarr||/failed|blocked|unknown|attention|removed/i.test(`${row.status||''} ${label}`)))return {label:row.removed_from_lidarr?'Removed from Lidarr':row.download_error||row.error||row.downloads?.find((d:any)=>d.error)?.error||(/failed|blocked|unknown/i.test(row.status||'')?String(row.status).replace(/_/g,' '):label),icon:'!',tone:'error'}
 if(group==='Cancelled / Failed')return {label,icon:'!',tone:'error'}
 if(row.plex_available||/^(Available|In Library|In Plex|Completed)$/.test(label))return {label,icon:'✓',tone:'available'}
 if((row.error&&row.status!=='search_pending')||/failed|blocked|attention|removed/i.test(label))return {label,icon:'!',tone:'error'}
 if(/imported|awaiting plex|importing/i.test(label))return {label:/imported/i.test(label)?'Waiting for Plex':label,icon:'◷',tone:'imported'}
 if(/download|searching|progress/i.test(label))return {label,icon:'↓',tone:'progress'}
 if(/not available|missing/i.test(label))return {label,icon:'○',tone:'missing'}
 return {label,icon:'◷',tone:'pending'}
}
export function CoverStatus({row}:{row:any}){const status=coverStatus(row);return <span className={'cover-status '+status.tone} role="img" aria-label={status.label} title={status.label}>{status.icon}</span>}
export default function AlbumCover({src,children}:{src?:string;children?:ReactNode}){
 const [failed,setFailed]=useState(false)
 useEffect(()=>setFailed(false),[src])
 return <div className="album-cover">{src&&!failed?<img src={src} alt="" loading="lazy" onError={()=>setFailed(true)}/>:<div className="album-art-placeholder" aria-hidden="true">♫</div>}{children}</div>
}
