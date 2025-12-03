import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { 
  Camera, 
  Plus, 
  Trash2, 
  Play, 
  Square, 
  Settings,
  Video,
  Eye,
  Monitor
} from 'lucide-react'
import { camerasApi, Camera as CameraType, CameraCreate } from '../api'

function Cameras() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [newCamera, setNewCamera] = useState<CameraCreate>({
    name: '',
    url: '',
    recording_enabled: false,
    audio_enabled: false,
    motion_detection_enabled: true,
    motion_sensitivity: 25,
    motion_min_area: 500,
    motion_cooldown: 30,
    save_snapshots: true,
    save_video_clips: false,
    video_clip_duration: 10,
    notification_cooldown: 60,
  })

  const queryClient = useQueryClient()

  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.getAll,
  })

  const createMutation = useMutation({
    mutationFn: camerasApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      setShowAddModal(false)
      setNewCamera({
        name: '',
        url: '',
        recording_enabled: false,
        audio_enabled: false,
        motion_detection_enabled: true,
        motion_sensitivity: 25,
        motion_min_area: 500,
        motion_cooldown: 30,
        save_snapshots: true,
        save_video_clips: false,
        video_clip_duration: 10,
        notification_cooldown: 60,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: camerasApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
    },
  })

  const controlMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) =>
      camerasApi.control(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
    },
  })

  const handleCreateCamera = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(newCamera)
  }

  const handleDeleteCamera = (id: number) => {
    if (confirm('Are you sure you want to delete this camera?')) {
      deleteMutation.mutate(id)
    }
  }

  const handleToggleRecording = (camera: CameraType) => {
    const action = camera.recording_enabled ? 'stop_recording' : 'start_recording'
    controlMutation.mutate({ id: camera.id, action })
  }

  const handleToggleDetection = (camera: CameraType) => {
    const action = camera.motion_detection_enabled ? 'stop_detection' : 'start_detection'
    controlMutation.mutate({ id: camera.id, action })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Cameras</h1>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="h-5 w-5 mr-2" />
          Add Camera
        </button>
      </div>

      {/* Camera List */}
      {cameras && cameras.length > 0 ? (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Camera
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Recording
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Detection
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {cameras.map((camera) => (
                <tr key={camera.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Camera className="h-8 w-8 text-gray-400 mr-3" />
                      <div>
                        <div className="font-medium text-gray-900">{camera.name}</div>
                        <div className="text-sm text-gray-500 truncate max-w-xs">
                          {camera.url}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
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
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleToggleRecording(camera)}
                      className={`p-2 rounded ${
                        camera.recording_enabled
                          ? 'bg-green-100 text-green-600 hover:bg-green-200'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                      title={camera.recording_enabled ? 'Stop recording' : 'Start recording'}
                    >
                      {camera.recording_enabled ? (
                        <Square className="h-5 w-5" />
                      ) : (
                        <Play className="h-5 w-5" />
                      )}
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleToggleDetection(camera)}
                      className={`p-2 rounded ${
                        camera.motion_detection_enabled
                          ? 'bg-blue-100 text-blue-600 hover:bg-blue-200'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                      title={
                        camera.motion_detection_enabled
                          ? 'Disable detection'
                          : 'Enable detection'
                      }
                    >
                      <Eye className="h-5 w-5" />
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <div className="flex items-center justify-end space-x-2">
                      <Link
                        to={`/cameras/${camera.id}`}
                        className="p-2 text-gray-600 hover:text-green-600 hover:bg-green-50 rounded"
                        title="Live View"
                      >
                        <Monitor className="h-5 w-5" />
                      </Link>
                      <Link
                        to={`/cameras/${camera.id}/settings`}
                        className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="Settings"
                      >
                        <Settings className="h-5 w-5" />
                      </Link>
                      <Link
                        to={`/recordings?camera=${camera.id}`}
                        className="p-2 text-gray-600 hover:text-purple-600 hover:bg-purple-50 rounded"
                        title="Recordings"
                      >
                        <Video className="h-5 w-5" />
                      </Link>
                      <button
                        onClick={() => handleDeleteCamera(camera.id)}
                        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <Camera className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900">No cameras</h3>
          <p className="mt-1 text-gray-500">
            Add your first camera to get started
          </p>
        </div>
      )}

      {/* Add Camera Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div
              className="fixed inset-0 bg-gray-500 bg-opacity-75"
              onClick={() => setShowAddModal(false)}
            />
            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">
                Add Camera
              </h2>
              <form onSubmit={handleCreateCamera}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Name
                    </label>
                    <input
                      type="text"
                      value={newCamera.name}
                      onChange={(e) =>
                        setNewCamera({ ...newCamera, name: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Front Door Camera"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Stream URL
                    </label>
                    <input
                      type="text"
                      value={newCamera.url}
                      onChange={(e) =>
                        setNewCamera({ ...newCamera, url: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                      placeholder="rtsp://user:pass@192.168.1.100:554/stream or /dev/video0"
                      required
                    />
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium text-gray-900 mb-2">Detection Settings</h4>
                    <div className="space-y-3">
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={newCamera.motion_detection_enabled}
                          onChange={(e) =>
                            setNewCamera({
                              ...newCamera,
                              motion_detection_enabled: e.target.checked,
                            })
                          }
                          className="h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">
                          Enable motion detection
                        </span>
                      </label>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={newCamera.save_snapshots}
                          onChange={(e) =>
                            setNewCamera({
                              ...newCamera,
                              save_snapshots: e.target.checked,
                            })
                          }
                          className="h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">
                          Save snapshots on motion
                        </span>
                      </label>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={newCamera.save_video_clips}
                          onChange={(e) =>
                            setNewCamera({
                              ...newCamera,
                              save_video_clips: e.target.checked,
                            })
                          }
                          className="h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">
                          Save video clips on motion (with audio)
                        </span>
                      </label>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium text-gray-900 mb-2">Recording Settings</h4>
                    <div className="space-y-3">
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={newCamera.recording_enabled}
                          onChange={(e) =>
                            setNewCamera({
                              ...newCamera,
                              recording_enabled: e.target.checked,
                            })
                          }
                          className="h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">
                          Continuous recording
                        </span>
                      </label>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={newCamera.audio_enabled}
                          onChange={(e) =>
                            setNewCamera({
                              ...newCamera,
                              audio_enabled: e.target.checked,
                            })
                          }
                          className="h-4 w-4 text-blue-600 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">
                          Record audio
                        </span>
                      </label>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Sensitivity: {newCamera.motion_sensitivity}%
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={newCamera.motion_sensitivity}
                      onChange={(e) =>
                        setNewCamera({
                          ...newCamera,
                          motion_sensitivity: parseInt(e.target.value),
                        })
                      }
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Notification cooldown (seconds)
                    </label>
                    <input
                      type="number"
                      value={newCamera.notification_cooldown}
                      onChange={(e) =>
                        setNewCamera({
                          ...newCamera,
                          notification_cooldown: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                      min="0"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Minimum time between Telegram notifications
                    </p>
                  </div>
                </div>
                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {createMutation.isPending ? 'Adding...' : 'Add Camera'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Cameras
