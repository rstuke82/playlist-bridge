export type Job = {id:string;action:string;status:string;progress:string;error?:string;payload:any;result:any;created_at:string;started_at?:string;finished_at?:string}
export const activeJob = (job:Job) => ['queued','running','cancelling'].includes(job.status)
export type Playlist = {
  key: string
  name: string
  source: string
  source_url: string
  favorite: boolean
  auto_sync: boolean
  added_at?: string | null
  last_synced?: string | null
  health?: PlaylistHealth
  health_attempt?: {attempted_at:string; error:string|null}
  saved_matches: number
  unresolved: number
  lost: number
  ignored: number
}

export type PlaylistHealth = {
  key: string
  name: string
  source: string
  source_tracks: number
  plex_playlist_tracks: number
  matched_in_library: number
  unresolved: number
  ignored: number
  missing_from_plex_playlist: number
  extra_in_plex_playlist: number
  source_added_since_last_sync: number
  source_removed_since_last_sync: number
  healthy: boolean
  checked_at: string
  drift_details?: Record<string, any[]>
  read_only: boolean
}

export type PlexSettings = {
  url: string
  token_configured: boolean
  token_hint: string
  music_library_key: string
  music_library_name: string
  connected?: boolean
}

export type PlexLibrary = {
  key: string
  name: string
}

export type MissingTrack = {
  title: string
  artist: string
  album?: string
  occurrence_count: number
  playlist_count: number
  lost_occurrence_count?: number
  playlists: string[]
  last_checked?: string | null
  memberships: {key:string;name:string;count:number;last_checked?:string}[]
}

export type Candidate = {
  plex_id: string
  title: string
  artist: string
  album: string
  score: number
  title_score: number
  artist_score: number
  album_score?: number | null
  album_penalty: number
  title_variant_penalty: number
  release_intent_penalty: number
}

const pending = new Map<string, Promise<any>>()
async function send<T>(path:string, init?:RequestInit):Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(()=>controller.abort(), path.endsWith('/detail') ? 65000 : 30000)
  try {
    const response = await fetch(path, {...init, signal:controller.signal,
      headers:{'Content-Type':'application/json', ...init?.headers}})
    if (!response.ok) {
      const body = await response.json().catch(()=>({}))
      throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}). Check Settings → Logs.`)
    }
    const result = await response.json()
    if (init?.method && init.method !== 'GET') window.dispatchEvent(new Event('jobs-refresh'))
    return result
  } catch (error:any) {
    if (error.name === 'AbortError') throw new Error('Request timed out. Check source/Plex connectivity and retry.')
    throw error
  } finally { clearTimeout(timer) }
}
function request<T>(path:string, init?:RequestInit):Promise<T> {
  if (init?.method && init.method !== 'GET') return send<T>(path,init)
  // Share in-flight reads, including React StrictMode's setup/cleanup/setup cycle.
  const existing = pending.get(path)
  if (existing) return existing
  const promise = send<T>(path,init).finally(()=>pending.delete(path))
  pending.set(path,promise)
  return promise
}

export const api = {
  jobs: () => request<Job[]>('/api/jobs'),
  enqueue: (action:string,payload:any={}) => request<Job>('/api/jobs',{method:'POST',body:JSON.stringify({action,payload})}),
  cancel: (id:string) => request<Job>(`/api/jobs/${id}/cancel`,{method:'POST'}),
  schedules: () => request<any[]>('/api/schedules'),
  saveSchedule: (data:any,id?:string) => request<any>(`/api/schedules${id?`/${id}`:''}`,{method:id?'PUT':'POST',body:JSON.stringify(data)}),
  deleteSchedule: (id:string) => request<any>(`/api/schedules/${id}`,{method:'DELETE'}),
  runSchedule: (id:string) => request<Job>(`/api/schedules/${id}/run`,{method:'POST'}),
  ignore: (data:any) => request<any>('/api/missing/ignore',{method:'POST',body:JSON.stringify(data)}),
  ignored: () => request<any[]>('/api/ignored'),
  restoreIgnore: (data:any) => request<any>('/api/ignored/restore',{method:'POST',body:JSON.stringify(data)}),
  search: (q:string) => request<any>(`/api/search?q=${encodeURIComponent(q)}`),
  clearLogs: () => request<any>('/api/settings/logs',{method:'DELETE'}),
  logs: (level:string,action='') => request<{entries:{id:number;created_at:string;level:string;operation:string;message:string}[];retention:number}>(`/api/settings/logs?limit=200${level?`&level=${level}`:''}${action?`&action=${encodeURIComponent(action)}`:''}`),
  detail: (key: string) => request<any>(`/api/playlists/${encodeURIComponent(key)}/detail`),
  health: () => request<any>('/api/health'),
  playlists: () => request<Playlist[]>('/api/playlists'),
  playlistHealth: (key: string) => request<PlaylistHealth>(`/api/playlists/${encodeURIComponent(key)}/health`),
  updatePlaylist: (key: string, body: Partial<Pick<Playlist, 'favorite' | 'auto_sync'>>) =>
    request<Playlist>(`/api/playlists/${encodeURIComponent(key)}`, {
      method: 'PATCH', body: JSON.stringify(body),
    }),
  analyzePlaylist: (url: string) => request<any>('/api/playlists/analyze', {
    method: 'POST', body: JSON.stringify({ url }),
  }),
  addPlaylist: (body: { url: string; favorite: boolean; auto_sync: boolean }) =>
    request<Playlist>('/api/playlists', { method: 'POST', body: JSON.stringify(body) }),
  syncAll: () => request<any>('/api/sync/all', { method: 'POST' }),
  syncFavorites: () => request<any>('/api/sync/favorites', { method: 'POST' }),
  syncOne: (key: string) => request<any>(`/api/sync/${encodeURIComponent(key)}`, { method: 'POST' }),
  missing: (scope: 'all' | 'favorites' = 'all') => request<MissingTrack[]>(`/api/missing?scope=${scope}`),
  candidates: (track: Pick<MissingTrack, 'title' | 'artist' | 'album'> & { query?: string }) =>
    request<Candidate[]>('/api/missing/candidates', { method: 'POST', body: JSON.stringify(track) }),
  saveMatch: (track: MissingTrack, plex_id: string, options: {playlist_keys?: string[]; replace_playlist_key?: string} = {}) =>
    request<Job>('/api/missing/match', {
      method: 'POST',
      body: JSON.stringify({ title: track.title, artist: track.artist, album: track.album || '', plex_id, ...options }),
    }),
  plexSettings: () => request<PlexSettings>('/api/settings/plex'),
  discoverPlex: (body: { url: string; token: string }) =>
    request<{ libraries: PlexLibrary[] }>('/api/settings/plex/discover', {
      method: 'POST', body: JSON.stringify(body),
    }),
  savePlex: (body: { url: string; token: string; music_library_key: string }) =>
    request<PlexSettings>('/api/settings/plex', {
      method: 'PUT', body: JSON.stringify(body),
    }),
}
