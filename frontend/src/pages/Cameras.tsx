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
  Eye
} from 'lucide-react'
import { camerasApi, Camera as CameraType, CameraCreate } from '../api'

function Cameras() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [newCamera, setNewCamera] = useState<CameraCreate>({
    name: '',
    url: '',
    recording_enabled: true,
    audio_enabled: true,
    motion_detection_enabled: true,
    motion_sensitivity: 25,
    motion_min_area: 500,
    motion_cooldown: 30,
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
        recording_enabled: true,
        audio_enabled: true,
        motion_detection_enabled: true,
        motion_sensitivity: 25,
        motion_min_area: 500,
        motion_cooldown: 30,
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
    if (confirm('Вы уверены что хотите удалить камеру?')) {
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
        <h1 className="text-2xl font-bold text-gray-900">Камеры</h1>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="h-5 w-5 mr-2" />
          Добавить камеру
        </button>
      </div>

      {/* Camera List */}
      {cameras && cameras.length > 0 ? (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Камера
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Статус
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Запись
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Детекция
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Действия
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
                        ? 'Записывает'
                        : camera.status === 'online'
                        ? 'Онлайн'
                        : camera.status === 'error'
                        ? 'Ошибка'
                        : 'Офлайн'}
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
                      title={camera.recording_enabled ? 'Остановить запись' : 'Начать запись'}
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
                          ? 'Отключить детекцию'
                          : 'Включить детекцию'
                      }
                    >
                      <Eye className="h-5 w-5" />
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <div className="flex items-center justify-end space-x-2">
                      <Link
                        to={`/cameras/${camera.id}`}
                        className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="Настройки"
                      >
                        <Settings className="h-5 w-5" />
                      </Link>
                      <Link
                        to={`/recordings?camera=${camera.id}`}
                        className="p-2 text-gray-600 hover:text-purple-600 hover:bg-purple-50 rounded"
                        title="Записи"
                      >
                        <Video className="h-5 w-5" />
                      </Link>
                      <button
                        onClick={() => handleDeleteCamera(camera.id)}
                        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Удалить"
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
          <h3 className="mt-2 text-lg font-medium text-gray-900">Нет камер</h3>
          <p className="mt-1 text-gray-500">
            Добавьте первую камеру для начала работы
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
                Добавить камеру
              </h2>
              <form onSubmit={handleCreateCamera}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Название
                    </label>
                    <input
                      type="text"
                      value={newCamera.name}
                      onChange={(e) =>
                        setNewCamera({ ...newCamera, name: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Камера во дворе"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      URL потока
                    </label>
                    <input
                      type="text"
                      value={newCamera.url}
                      onChange={(e) =>
                        setNewCamera({ ...newCamera, url: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                      placeholder="rtsp://user:pass@192.168.1.100:554/stream"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
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
                        Включить запись
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
                        Записывать аудио
                      </span>
                    </label>
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
                        Детекция движения
                      </span>
                    </label>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Чувствительность: {newCamera.motion_sensitivity}%
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
                      Cooldown между уведомлениями (сек)
                    </label>
                    <input
                      type="number"
                      value={newCamera.motion_cooldown}
                      onChange={(e) =>
                        setNewCamera({
                          ...newCamera,
                          motion_cooldown: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                      min="0"
                    />
                  </div>
                </div>
                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {createMutation.isPending ? 'Добавление...' : 'Добавить'}
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
