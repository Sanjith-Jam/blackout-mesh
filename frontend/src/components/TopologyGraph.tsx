import { useMemo } from 'react';
import ReactFlow, { Background, Controls, Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { Snapshot } from '../types';

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
      data: { label: `Source\n${source.capacity_w} W` },
      style: { background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '10px', textAlign: 'center', fontWeight: 'bold' }
    });

    // Feeders
    nds.push({
      id: 'feeder_A',
      position: { x: 200, y: 150 },
      data: { label: `Feeder A\nLimit: ${feeder_limits_w.A} W` },
      style: { background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px', textAlign: 'center' }
    });
    nds.push({
      id: 'feeder_B',
      position: { x: 600, y: 150 },
      data: { label: `Feeder B\nLimit: ${feeder_limits_w.B} W` },
      style: { background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px', textAlign: 'center' }
    });

    // Services for Feeder A
    const feederAServices = services.filter(s => s.feeder === 'A');
    feederAServices.forEach((s, i) => {
      nds.push({
        id: `svc_${s.id}`,
        position: { x: 50 + i * 150, y: 280 },
        data: { label: `${s.id}\n${s.watts} W\n${s.modeled_served ? 'Served' : 'Shed'}` },
        style: { 
          background: s.modeled_served ? '#dbeafe' : '#fee2e2', 
          border: `1px solid ${s.modeled_served ? '#bfdbfe' : '#fecaca'}`,
          borderRadius: '8px', padding: '10px', textAlign: 'center', fontSize: '0.8rem' 
        }
      });
    });

    // Services for Feeder B
    const feederBServices = services.filter(s => s.feeder === 'B');
    feederBServices.forEach((s, i) => {
      nds.push({
        id: `svc_${s.id}`,
        position: { x: 450 + i * 150, y: 280 },
        data: { label: `${s.id}\n${s.watts} W\n${s.modeled_served ? 'Served' : 'Shed'}` },
        style: { 
          background: s.modeled_served ? '#dbeafe' : '#fee2e2', 
          border: `1px solid ${s.modeled_served ? '#bfdbfe' : '#fecaca'}`,
          borderRadius: '8px', padding: '10px', textAlign: 'center', fontSize: '0.8rem' 
        }
      });
    });

    return nds;
  }, [services, source.capacity_w, feeder_limits_w]);

  const edges: Edge[] = useMemo(() => {
    const eds: Edge[] = [];
    eds.push({ id: 'e_source_A', source: 'source', target: 'feeder_A', animated: true });
    eds.push({ id: 'e_source_B', source: 'source', target: 'feeder_B', animated: true });

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
    <div style={{ height: '400px', width: '100%', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#ccc" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
