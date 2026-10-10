import { useMemo } from 'react';
import ReactFlow, { Background, Controls, Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { Snapshot, servedWatts, serviceStatus } from '../types';

interface TopologyGraphProps {
  snapshot: Snapshot;
}

export default function TopologyGraph({ snapshot }: TopologyGraphProps) {
  const { services, source, feeder_limits_w } = snapshot;

  const nodes: Node[] = useMemo(() => {
    const nds: Node[] = [];

    // Source node
    nds.push({
      id: 'source',
      position: { x: 400, y: 50 },
      width: 190,
      height: 74,
      data: { label: `Source\n${source.capacity_w} W` },
      style: { width: 190, height: 74, background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '10px', textAlign: 'center', whiteSpace: 'pre-line', fontWeight: 'bold' }
    });

    // Feeders
    nds.push({
      id: 'feeder_A',
      position: { x: 200, y: 150 },
      width: 190,
      height: 68,
      data: { label: `Feeder A\nLimit: ${feeder_limits_w.A} W` },
      style: { width: 190, height: 68, background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px', textAlign: 'center', whiteSpace: 'pre-line' }
    });
    nds.push({
      id: 'feeder_B',
      position: { x: 600, y: 150 },
      width: 190,
      height: 68,
      data: { label: `Feeder B\nLimit: ${feeder_limits_w.B} W` },
      style: { width: 190, height: 68, background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px', textAlign: 'center', whiteSpace: 'pre-line' }
    });

    // Services for Feeder A
    const feederAServices = services.filter(s => s.feeder === 'A');
    feederAServices.forEach((s, i) => {
      nds.push({
        id: `svc_${s.id}`,
        position: { x: 40 + i * 160, y: 280 },
        width: 140,
        height: 76,
        data: { label: `${s.id}\n${servedWatts(s)} / ${s.watts} W\n${serviceStatus(s)}` },
        style: {
          width: 140, height: 76,
          background: s.modeled_served ? '#dbeafe' : '#fee2e2',
          border: `1px solid ${s.modeled_served ? '#bfdbfe' : '#fecaca'}`,
          borderRadius: '8px', padding: '10px', textAlign: 'center', whiteSpace: 'pre-line', fontSize: '0.8rem'
        }
      });
    });

    // Services for Feeder B
    const feederBServices = services.filter(s => s.feeder === 'B');
    feederBServices.forEach((s, i) => {
      nds.push({
        id: `svc_${s.id}`,
        position: { x: 560 + i * 160, y: 280 },
        width: 140,
        height: 76,
        data: { label: `${s.id}\n${servedWatts(s)} / ${s.watts} W\n${serviceStatus(s)}` },
        style: {
          width: 140, height: 76,
          background: s.modeled_served ? '#dbeafe' : '#fee2e2',
          border: `1px solid ${s.modeled_served ? '#bfdbfe' : '#fecaca'}`,
          borderRadius: '8px', padding: '10px', textAlign: 'center', whiteSpace: 'pre-line', fontSize: '0.8rem'
        }
      });
    });

    return nds;
  }, [services, source.capacity_w, feeder_limits_w]);

  const edges: Edge[] = useMemo(() => {
    const eds: Edge[] = [];
    eds.push({ id: 'e_source_A', source: 'source', target: 'feeder_A', animated: services.some(s => s.feeder === 'A' && s.modeled_served) });
    eds.push({ id: 'e_source_B', source: 'source', target: 'feeder_B', animated: services.some(s => s.feeder === 'B' && s.modeled_served) });

    services.forEach(s => {
      eds.push({
        id: `e_feeder${s.feeder}_${s.id}`,
        source: `feeder_${s.feeder}`,
        target: `svc_${s.id}`,
        animated: s.modeled_served,
        style: { stroke: s.modeled_served ? '#3b82f6' : '#ef4444' }
      });
    });

    return eds;
  }, [services]);

  return (
    <div style={{ height: '400px', width: '100%', overflow: 'hidden', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#ccc" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
