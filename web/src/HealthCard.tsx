import { Playlist } from './api'
export const stamp=(value?:string|null)=>value?new Date(value).toLocaleString():'Never'
export default function HealthCard({playlist}:{playlist:Playlist}){
  const h=playlist.health
  const reasons=h?[
    [h.unresolved,'unresolved source tracks'],[h.missing_from_plex_playlist,'tracks missing from Plex playlist'],
    [h.extra_in_plex_playlist,'extra tracks in Plex playlist'],[h.source_added_since_last_sync,'source additions since sync'],
    [h.source_removed_since_last_sync,'source removals since sync']
  ].filter(([count])=>Number(count)>0):[]
  return <div className="health-card">
    <p className="timestamps">Last synced: {stamp(playlist.last_synced)}<br/>Last successful health check: {stamp(h?.checked_at)}</p>
    {playlist.health_attempt?.error&&<p role="alert" className="health-error">{playlist.health_attempt.error}<br/>Last attempt: {stamp(playlist.health_attempt.attempted_at)}. Previous successful results are retained. <a href="#settings">Open Settings</a></p>}
    {h&&!h.healthy&&<p className="drift-summary"><strong>Drift:</strong> {reasons.map(([count,label])=>`${count} ${label}`).join(' · ')||'See health details'}</p>}
    <details><summary>Health details · {h?(h.healthy?'Healthy':'Drift detected'):'Not checked'}</summary>
      <div className="health-grid">{[['Source',h?.source_tracks],['Plex playlist',h?.plex_playlist_tracks],['Matched',h?.matched_in_library],['Unresolved',h?.unresolved],['Ignored',h?.ignored],['Missing from Plex',h?.missing_from_plex_playlist],['Extra in Plex',h?.extra_in_plex_playlist]].map(([label,value])=><div className="health-metric" key={label}><span>{label}</span><strong>{value??'--'}</strong></div>)}</div>
      {h?.drift_details?Object.entries(h.drift_details).filter(([,rows])=>rows.length).map(([kind,rows])=><details className="drift-list" key={kind}><summary>{{missing_from_plex:'Missing from Plex playlist',extra_in_plex:'Extra in Plex playlist',unresolved:'Unresolved source tracks',source_added:'Added to source',source_removed:'Removed from source'}[kind]||kind} ({rows.reduce((n,t)=>n+(t.count||1),0)})</summary><ul>{rows.map((t,i)=><li key={i}>{t.title||t.plex_id} {t.artist&&`— ${t.artist}`} {t.count>1&&`× ${t.count}`}</li>)}</ul></details>):h&&!h.healthy&&<p>Run Check Health again to populate track-level differences from this beta.</p>}
    </details>
  </div>
}
