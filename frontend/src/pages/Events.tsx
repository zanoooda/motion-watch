import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  AlertCircle, 
  Camera, 
  Clock, 
  Image,
  Video,
  Filter
} from 'lucide-react'
import { eventsApi, camerasApi, Event } from '../api'
import { format } from 'date-fns'

function Events() {
  const [cameraFilter, setCameraFilter] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const limit = 20

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['events', cameraFilter, page],
    queryFn: () => eventsApi.getAll({ 
      camera_id: cameraFilter || undefined, 
      limit, 
      offset: (page - 1) * limit 
    }),
  })

  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.getAll,
  })

  if (eventsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Motion Events</h1>
        
        {/* Filters */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center">
            <Filter className="h-5 w-5 text-gray-400 mr-2" />
            <select
              value={cameraFilter || ''}
              onChange={(e) => {
                setCameraFilter(e.target.value ? parseInt(e.target.value) : null)
                setPage(1)
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All cameras</option>
              {cameras?.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {events && events.length > 0 ? (
        <>
          {/* Events Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {events.map((event) => (
              <EventCard key={event.id} event={event} cameras={cameras || []} />
            ))}
          </div>

          {/* Pagination */}
          <div className="mt-6 flex items-center justify-center space-x-4">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-gray-600">Page {page}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={events.length < limit}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </>
      ) : (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <AlertCircle className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900">No events</h3>
          <p className="mt-1 text-gray-500">
            Motion events will appear here when detected
          </p>
        </div>
      )}
    </div>
  )
}

// Event Card Component
function EventCard({ event, cameras }: { event: Event; cameras: any[] }) {
  const camera = cameras.find(c => c.id === event.camera_id)
  const [imageError, setImageError] = useState(false)

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition-shadow">
      {/* Snapshot */}
      <div className="aspect-video bg-gray-100 relative">
        {event.snapshot_path && !imageError ? (
          <img
            src={`/api/events/${event.id}/snapshot`}
            alt="Motion snapshot"
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Image className="h-12 w-12 text-gray-300" />
          </div>
        )}
        
        {/* Confidence badge */}
        <div className="absolute top-2 right-2">
          <span className="px-2 py-1 bg-black/60 text-white text-xs rounded">
            {Math.round(event.confidence * 100)}% confidence
          </span>
        </div>

        {/* Video clip indicator */}
        {event.video_clip_path && (
          <div className="absolute bottom-2 right-2">
            <span className="px-2 py-1 bg-green-500 text-white text-xs rounded flex items-center">
              <Video className="h-3 w-3 mr-1" />
              Clip
            </span>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-4">
        <div className="flex items-center text-gray-600 mb-2">
          <Camera className="h-4 w-4 mr-2" />
          <span className="text-sm font-medium">{camera?.name || 'Unknown camera'}</span>
        </div>
        <div className="flex items-center text-gray-500 text-sm">
          <Clock className="h-4 w-4 mr-2" />
          {format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}
        </div>
        
        {/* Actions */}
        <div className="mt-3 flex items-center space-x-2">
          {event.snapshot_path && (
            <a
              href={`/api/events/${event.id}/snapshot`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
            >
              View Snapshot
            </a>
          )}
          {event.video_clip_path && (
            <a
              href={`/api/events/${event.id}/clip`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
            >
              View Clip
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

export default Events
