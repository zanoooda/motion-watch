import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  ArrowLeft, 
  Camera, 
  Eye, 
  Video, 
  Settings,
  RefreshCw
} from 'lucide-react'
import { camerasApi, Camera as CameraType, eventsApi } from '../api'

function CameraDetail() {
  const { id } = useParams<{ id: string }>()
  const cameraId = parseInt(id || '0')
  const [isLive, setIsLive] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  
  const queryClient = useQueryClient()

  const { data: camera, isLoading: cameraLoading } = useQuery({
    queryKey: ['camera', cameraId],
    queryFn: () => camerasApi.getById(cameraId),
    enabled: cameraId > 0,
  })

  const { data: events } = useQuery({
    queryKey: ['events', cameraId],
    queryFn: () => eventsApi.getAll({ camera_id: cameraId, limit: 10 }),
    enabled: cameraId > 0,
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<CameraType>) => camerasApi.update(cameraId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['camera', cameraId] })
      setShowSettings(false)
    },
  })

  // Auto-refresh snapshot when live
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (isLive && camera) {
      interval = setInterval(() => {
        setRefreshKey((k: number) => k + 1)
      }, 500) // Refresh every 500ms for live view
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isLive, camera])

  const handleSaveSettings = (settings: Partial<CameraType>) => {
    updateMutation.mutate(settings)
  }

  if (cameraLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!camera) {
    return (
      <div className="text-center py-12">
        <Camera className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-lg font-medium text-gray-900">Camera not found</h3>
        <Link to="/cameras" className="text-blue-600 hover:underline mt-2 inline-block">
          Back to cameras
        </Link>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <Link to="/cameras" className="mr-4 p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{camera.name}</h1>
            <p className="text-sm text-gray-500">{camera.url}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg ${showSettings ? 'bg-blue-100 text-blue-600' : 'hover:bg-gray-100 text-gray-600'}`}
          >
            <Settings className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live View */}
        <div className="lg:col-span-2">
          <div className="bg-black rounded-lg overflow-hidden relative">
            <div className="aspect-video flex items-center justify-center">
              <img
                ref={imgRef}
                key={refreshKey}
                src={`/api/cameras/${camera.id}/snapshot?t=${Date.now()}`}
                alt={camera.name}
                className="w-full h-full object-contain"
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.src = '/placeholder-camera.svg'
                }}
              />
            </div>
            
            {/* Controls overlay */}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => setIsLive(!isLive)}
                    className={`px-3 py-1 rounded text-sm font-medium ${
                      isLive ? 'bg-red-600 text-white' : 'bg-white/20 text-white'
                    }`}
                  >
                    {isLive ? (
                      <>
                        <span className="inline-block w-2 h-2 bg-white rounded-full mr-2 animate-pulse"></span>
                        LIVE
                      </>
                    ) : (
                      'PAUSED'
                    )}
                  </button>
                  <button
                    onClick={() => setRefreshKey(k => k + 1)}
                    className="p-2 text-white hover:bg-white/20 rounded"
                    title="Refresh"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex items-center space-x-2">
                  <span
                    className={`px-2 py-1 text-xs rounded ${
                      camera.motion_detection_enabled
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-500 text-white'
                    }`}
                  >
                    {camera.motion_detection_enabled ? 'Detection ON' : 'Detection OFF'}
                  </span>
                  <span
                    className={`px-2 py-1 text-xs rounded ${
                      camera.recording_enabled
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-500 text-white'
                    }`}
                  >
                    {camera.recording_enabled ? 'Recording ON' : 'Recording OFF'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar - Settings or Recent Events */}
        <div className="lg:col-span-1">
          {showSettings ? (
            <CameraSettings camera={camera} onSave={handleSaveSettings} isPending={updateMutation.isPending} />
          ) : (
            <RecentEvents events={events || []} />
          )}
        </div>
      </div>
    </div>
  )
}

// Camera Settings Component
function CameraSettings({ 
  camera, 
  onSave, 
  isPending 
}: { 
  camera: CameraType
  onSave: (settings: Partial<CameraType>) => void
  isPending: boolean
}) {
  const [settings, setSettings] = useState({
    motion_detection_enabled: camera.motion_detection_enabled,
    motion_sensitivity: camera.motion_sensitivity,
    motion_min_area: camera.motion_min_area,
    motion_cooldown: camera.motion_cooldown,
    save_snapshots: camera.save_snapshots,
    save_video_clips: camera.save_video_clips,
    video_clip_duration: camera.video_clip_duration,
    recording_enabled: camera.recording_enabled,
    audio_enabled: camera.audio_enabled,
    notification_cooldown: camera.notification_cooldown,
  })

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Camera Settings</h3>
      
      <div className="space-y-4">
        {/* Detection Mode */}
        <div className="border-b pb-4">
          <h4 className="font-medium text-gray-700 mb-2 flex items-center">
            <Eye className="h-4 w-4 mr-2" />
            Motion Detection
          </h4>
          <label className="flex items-center mb-2">
            <input
              type="checkbox"
              checked={settings.motion_detection_enabled}
              onChange={(e) => setSettings({ ...settings, motion_detection_enabled: e.target.checked })}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="ml-2 text-sm text-gray-700">Enable motion detection</span>
          </label>
          <label className="flex items-center mb-2">
            <input
              type="checkbox"
              checked={settings.save_snapshots}
              onChange={(e) => setSettings({ ...settings, save_snapshots: e.target.checked })}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="ml-2 text-sm text-gray-700">Save snapshots on motion</span>
          </label>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={settings.save_video_clips}
              onChange={(e) => setSettings({ ...settings, save_video_clips: e.target.checked })}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="ml-2 text-sm text-gray-700">Save video clips with audio</span>
          </label>
        </div>

        {/* Sensitivity */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Sensitivity: {settings.motion_sensitivity}%
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={settings.motion_sensitivity}
            onChange={(e) => setSettings({ ...settings, motion_sensitivity: parseInt(e.target.value) })}
            className="w-full"
          />
        </div>

        {/* Video Clip Duration */}
        {settings.save_video_clips && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Video clip duration (seconds)
            </label>
            <input
              type="number"
              value={settings.video_clip_duration}
              onChange={(e) => setSettings({ ...settings, video_clip_duration: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              min="5"
              max="120"
            />
          </div>
        )}

        {/* Motion Cooldown */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Motion cooldown (seconds)
          </label>
          <input
            type="number"
            value={settings.motion_cooldown}
            onChange={(e) => setSettings({ ...settings, motion_cooldown: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            min="0"
          />
          <p className="text-xs text-gray-500 mt-1">Delay between motion event detection</p>
        </div>

        {/* Notification Cooldown */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notification cooldown (seconds)
          </label>
          <input
            type="number"
            value={settings.notification_cooldown}
            onChange={(e) => setSettings({ ...settings, notification_cooldown: parseInt(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            min="0"
          />
          <p className="text-xs text-gray-500 mt-1">Minimum time between Telegram notifications</p>
        </div>

        {/* Recording */}
        <div className="border-t pt-4">
          <h4 className="font-medium text-gray-700 mb-2 flex items-center">
            <Video className="h-4 w-4 mr-2" />
            Continuous Recording
          </h4>
          <label className="flex items-center mb-2">
            <input
              type="checkbox"
              checked={settings.recording_enabled}
              onChange={(e) => setSettings({ ...settings, recording_enabled: e.target.checked })}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="ml-2 text-sm text-gray-700">Enable recording</span>
          </label>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={settings.audio_enabled}
              onChange={(e) => setSettings({ ...settings, audio_enabled: e.target.checked })}
              className="h-4 w-4 text-blue-600 rounded"
            />
            <span className="ml-2 text-sm text-gray-700">Record audio</span>
          </label>
        </div>

        <button
          onClick={() => onSave(settings)}
          disabled={isPending}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {isPending ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

// Recent Events Component
function RecentEvents({ events }: { events: any[] }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Events</h3>
      
      {events.length > 0 ? (
        <div className="space-y-3">
          {events.map((event) => (
            <div key={event.id} className="flex items-start space-x-3 p-2 hover:bg-gray-50 rounded">
              {event.snapshot_path && (
                <img
                  src={`/api/events/${event.id}/snapshot`}
                  alt="Motion"
                  className="w-16 h-12 object-cover rounded"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">
                  Motion detected
                </p>
                <p className="text-xs text-gray-500">
                  {new Date(event.timestamp).toLocaleString()}
                </p>
                <p className="text-xs text-gray-500">
                  Confidence: {Math.round(event.confidence * 100)}%
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 text-sm">No recent events</p>
      )}
      
      <Link
        to="/events"
        className="mt-4 block text-center text-sm text-blue-600 hover:underline"
      >
        View all events
      </Link>
    </div>
  )
}

export default CameraDetail
