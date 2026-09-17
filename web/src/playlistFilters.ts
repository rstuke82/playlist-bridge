import { Playlist } from './api'
export const FILTER_STORAGE='bridge-playlist-filters'
export const playlistPredicates:Record<string,(p:Playlist)=>boolean>={
 'Favorites':p=>p.favorite,
 'Needs Attention':p=>!!p.health_attempt?.error||!!p.health&&!p.health.healthy||p.unresolved>0||p.lost>0,
 '100% Matched':p=>!!p.fully_matched,
 'Has Manual Matches':p=>(p.match_counts?.manual||0)>0,
 'Auto Sync On':p=>p.auto_sync,'Auto Sync Off':p=>!p.auto_sync,
 'Never Synced':p=>!p.last_synced,
}
export function openPlaylistView(filters:string[]=[]){
 const view={query:'',filters:normalizePlaylistFilters(filters),sort:'name'}
 try{localStorage.setItem(FILTER_STORAGE,JSON.stringify(view))}catch{}
 // The route carries intent even if browser storage is unavailable.
 location.hash=`playlists/view/${encodeURIComponent(JSON.stringify(view))}`
}

export function normalizePlaylistFilters(filters:string[]){return [...new Set(filters.map(f=>['Health Drift','Health Errors','Has Missing','Has LOST','Unhealthy'].includes(f)?'Needs Attention':f))].filter(f=>f in playlistPredicates)}
