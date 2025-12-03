import { useQuery } from '@tanstack/react-query'
import { Bell, Camera } from 'lucide-react'
import { eventsApi, camerasApi } from '../api'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'

function Events() {
  const { data: events, isLoading } = useQuery({
    queryKey: ['events'],
    queryFn: () => eventsApi.getAll({ limit: 100 }),
  })

  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.getAll,
  })

  const getCameraName = (cameraId: number) => {
    const camera = cameras?.find(c => c.id === cameraId)
    return camera?.name || `Камера ${cameraId}`
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
        <h1 className="text-2xl font-bold text-gray-900">События</h1>
      </div>

      {events && events.length > 0 ? (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="divide-y divide-gray-200">
            {events.map((event) => (
              <div key={event.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    {event.snapshot_path ? (
                      <img
                        src={`/api/media/${event.camera_id}/${event.timestamp.split('T')[0]}/snapshots/${event.snapshot_path.split('/').pop()}`}
                        alt="Snapshot"
                        className="h-20 w-32 object-cover rounded"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement
                          target.style.display = 'none'
                        }}
                      />
                    ) : (
                      <div className="h-20 w-32 bg-gray-200 rounded flex items-center justify-center">
                        <Camera className="h-8 w-8 text-gray-400" />
                      </div>
                    )}
                  </div>
                  <div className="ml-4 flex-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center">
                        <Bell className="h-5 w-5 text-yellow-500 mr-2" />
                        <span className="font-medium text-gray-900">
                          Движение обнаружено
                        </span>
                      </div>
                      <span className="text-sm text-gray-500">
                        {format(new Date(event.timestamp), 'dd MMM yyyy, HH:mm:ss', { locale: ru })}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-600">
                      {getCameraName(event.camera_id)}
                    </p>
                    <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
                      {event.confidence && (
                        <span>Уверенность: {event.confidence.toFixed(1)}%</span>
                      )}
                      <span>
                        {event.notification_sent ? '✓ Уведомление отправлено' : '○ Без уведомления'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <Bell className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900">Нет событий</h3>
          <p className="mt-1 text-gray-500">
            События детекции движения появятся здесь
          </p>
        </div>
      )}
    </div>
  )
}

export default Events
