import { SystemEvent } from '../types';
import './IncidentTimeline.css';

interface Props {
  events?: SystemEvent[];
}

export default function IncidentTimeline({ events = [] }: Props) {
  return (
    <div className="incident-timeline">
      <h3 style={{ margin: '0 0 10px 0', fontSize: '1.1rem' }}>Incident & Control Timeline</h3>
      <div className="timeline-container">
        {events.length === 0 ? (
          <div style={{ color: '#64748b', fontStyle: 'italic', padding: '10px' }}>No events recorded.</div>
        ) : (
          events.slice().reverse().map((evt, idx) => (
            <div key={idx} className="timeline-event">
              <div className="event-time">{new Date(evt.timestamp).toLocaleTimeString()}</div>
              <div className={`event-type type-${evt.type.toLowerCase().replace(/_/g, '-')}`}>{evt.type}</div>
              <div className="event-desc">{evt.description}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
