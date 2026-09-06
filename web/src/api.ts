export type Playlist = {
  key: string
  name: string
  source: string
  source_url: string
  favorite: boolean
  auto_sync: boolean
  last_synced?: string | null
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export const api = {
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
  candidates: (track: Pick<MissingTrack, 'title' | 'artist' | 'album'>) =>
    request<Candidate[]>('/api/missing/candidates', { method: 'POST', body: JSON.stringify(track) }),
  saveMatch: (track: MissingTrack, plex_id: string) =>
    request<{ affected: number; synced_playlists: number }>('/api/missing/match', {
      method: 'POST',
      body: JSON.stringify({ title: track.title, artist: track.artist, album: track.album || '', plex_id }),
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
