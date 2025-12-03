import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Camera {
  id: number
  name: string
  url: string
  status: 'offline' | 'online' | 'recording' | 'error'
  is_enabled: boolean
  recording_enabled: boolean
  audio_enabled: boolean
  motion_detection_enabled: boolean
  motion_sensitivity: number
  motion_min_area: number
  motion_cooldown: number
  detection_zones: string | null
  created_at: string
  updated_at: string | null
  last_seen: string | null
}

export interface CameraCreate {
  name: string
  url: string
  is_enabled?: boolean
  recording_enabled?: boolean
  audio_enabled?: boolean
  motion_detection_enabled?: boolean
  motion_sensitivity?: number
  motion_min_area?: number
  motion_cooldown?: number
}

export interface MotionEvent {
  id: number
  camera_id: number
  timestamp: string
  confidence: number | null
  snapshot_path: string | null
  video_clip_path: string | null
  notification_sent: boolean
}

export interface SystemSettings {
  telegram_configured: boolean
  storage_retention_days: number
  total_cameras: number
  active_cameras: number
  storage_used_gb: number
}

export interface StorageInfo {
  path: string
  total_gb: number
  used_gb: number
  free_gb: number
  recordings_used_gb: number
  cameras: { camera_dir: string; size_gb: number }[]
}

// API functions
export const camerasApi = {
  getAll: () => api.get<Camera[]>('/cameras/').then(res => res.data),
  getById: (id: number) => api.get<Camera>(`/cameras/${id}`).then(res => res.data),
  create: (data: CameraCreate) => api.post<Camera>('/cameras/', data).then(res => res.data),
  update: (id: number, data: Partial<CameraCreate>) => api.put<Camera>(`/cameras/${id}`, data).then(res => res.data),
  delete: (id: number) => api.delete(`/cameras/${id}`),
  control: (id: number, action: string) => api.post(`/cameras/${id}/control`, { action }).then(res => res.data),
}

export const eventsApi = {
  getAll: (params?: { camera_id?: number; limit?: number }) => 
    api.get<MotionEvent[]>('/events/', { params }).then(res => res.data),
  getRecent: (hours?: number) => 
    api.get<MotionEvent[]>('/events/recent', { params: { hours } }).then(res => res.data),
  getStats: (params?: { camera_id?: number; days?: number }) =>
    api.get('/events/stats', { params }).then(res => res.data),
  delete: (id: number) => api.delete(`/events/${id}`),
}

export const recordingsApi = {
  getSegments: (cameraId: number, date?: string) =>
    api.get(`/recordings/${cameraId}/segments`, { params: { date } }).then(res => res.data),
  getDates: (cameraId: number) =>
    api.get(`/recordings/${cameraId}/dates`).then(res => res.data),
  createClip: (data: { camera_id: number; start_time: string; end_time: string }) =>
    api.post('/recordings/create-clip', data).then(res => res.data),
}

export const settingsApi = {
  get: () => api.get<SystemSettings>('/settings/').then(res => res.data),
  update: (data: Record<string, unknown>) => api.put('/settings/', data).then(res => res.data),
  getStorage: () => api.get<StorageInfo>('/settings/storage').then(res => res.data),
  cleanup: (days: number) => api.post('/settings/cleanup', null, { params: { days } }).then(res => res.data),
}

export default api
