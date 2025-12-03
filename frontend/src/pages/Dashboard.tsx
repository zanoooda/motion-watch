import { useQuery } from '@tanstack/react-query'
import { Camera, Bell, HardDrive, Activity, Play } from 'lucide-react'
import { Link } from 'react-router-dom'
import { camerasApi, eventsApi, settingsApi } from '../api'

function Dashboard() {
  const { data: cameras, isLoading: camerasLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.getAll,
  })

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })

  const { data: recentEvents, isLoading: eventsLoading } = useQuery({
    queryKey: ['events', 'recent'],
    queryFn: () => eventsApi.getRecent(24),
  })

  const stats = [
    {
      name: 'Total Cameras',
      value: cameras?.length || 0,
      icon: Camera,
      color: 'bg-blue-500',
    },
    {
      name: 'Active Cameras',
      value: cameras?.filter(c => c.status === 'recording' || c.status === 'online').length || 0,
      icon: Activity,
      color: 'bg-green-500',
    },
    {
      name: 'Events (24h)',
      value: recentEvents?.length || 0,
      icon: Bell,
      color: 'bg-yellow-500',
    },
    {
      name: 'Storage Used (GB)',
      value: settings?.storage_used_gb?.toFixed(1) || '0',
      icon: HardDrive,
      color: 'bg-purple-500',
    },
  ]

  if (camerasLoading || settingsLoading || eventsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className={`${stat.color} p-3 rounded-lg`}>
                <stat.icon className="h-6 w-6 text-white" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Camera Grid with Live Preview */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Cameras</h2>
        </div>
        <div className="p-6">
          {cameras && cameras.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {cameras.map((camera) => (
                <Link
                  key={camera.id}
                  to={`/cameras/${camera.id}`}
                  className="border rounded-lg p-4 hover:border-blue-500 transition-colors block"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium text-gray-900">{camera.name}</h3>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        camera.status === 'recording'
                          ? 'bg-green-100 text-green-800'
                          : camera.status === 'online'
                          ? 'bg-blue-100 text-blue-800'
                          : camera.status === 'error'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {camera.status === 'recording'
                        ? 'Recording'
                        : camera.status === 'online'
                        ? 'Online'
                        : camera.status === 'error'
                        ? 'Error'
                        : 'Offline'}
                    </span>
                  </div>
                  <div className="aspect-video bg-gray-900 rounded mb-2 flex items-center justify-center relative overflow-hidden">
                    {camera.status !== 'offline' ? (
                      <>
                        <img
                          src={`/api/cameras/${camera.id}/snapshot`}
                          alt={camera.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            const target = e.target as HTMLImageElement
                            target.style.display = 'none'
                          }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-30 opacity-0 hover:opacity-100 transition-opacity">
                          <Play className="h-12 w-12 text-white" />
                        </div>
                      </>
                    ) : (
                      <Camera className="h-12 w-12 text-gray-600" />
                    )}
                  </div>
                  <div className="text-sm text-gray-500">
                    <p>
                      Detection: {camera.motion_detection_enabled ? 'On' : 'Off'}
                    </p>
                    <p>
                      Recording: {camera.recording_enabled ? 'On' : 'Off'}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <Camera className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No cameras</h3>
              <p className="mt-1 text-sm text-gray-500">
                Add your first camera to get started
              </p>
              <Link
                to="/cameras"
                className="mt-4 inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Add Camera
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Recent Events */}
      {recentEvents && recentEvents.length > 0 && (
        <div className="bg-white rounded-lg shadow mt-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Recent Events</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {recentEvents.slice(0, 5).map((event) => (
              <div key={event.id} className="px-6 py-4 flex items-center">
                <Bell className="h-5 w-5 text-yellow-500 mr-3" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">
                    Motion detected (Camera {event.camera_id})
                  </p>
                  <p className="text-sm text-gray-500">
                    {new Date(event.timestamp).toLocaleString()}
                  </p>
                </div>
                {event.snapshot_path && (
                  <img
                    src={`/api/snapshots/${event.id}`}
                    alt="Snapshot"
                    className="h-12 w-16 object-cover rounded"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
