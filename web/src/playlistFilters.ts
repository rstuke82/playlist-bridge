import { Playlist } from './api'
export const FILTER_STORAGE='bridge-playlist-filters'
export const playlistPredicates:Record<string,(p:Playlist)=>boolean>={
 'Favorites':p=>p.favorite,
 'Needs Attention':p=>!!p.health_attempt?.error||!!p.health&&!p.health.healthy||p.unresolved>0||p.lost>0,
 'Health Drift':p=>!!p.health&&!p.health.healthy,
 'Health Errors':p=>!!p.health_attempt?.error,
 '100% Matched':p=>!!p.fully_matched,
 'Has Manual Matches':p=>(p.match_counts?.manual||0)>0,
 'Auto Sync On':p=>p.auto_sync,'Auto Sync Off':p=>!p.auto_sync,
 'Has Missing':p=>p.unresolved>0,'Has LOST':p=>p.lost>0,'Never Synced':p=>!p.last_synced,
}
export function openPlaylistView(filters:string[]=[]){
 const view={query:'',filters,sort:'name'}
 try{localStorage.setItem(FILTER_STORAGE,JSON.stringify(view))}catch{}
 // The route carries intent even if browser storage is unavailable.
 location.hash=`playlists/view/${encodeURIComponent(JSON.stringify(view))}`
}
