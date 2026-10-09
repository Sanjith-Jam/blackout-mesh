import { useEffect, useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Edge, Handle, MarkerType, Node, NodeProps, Position } from 'reactflow';
import 'reactflow/dist/style.css';
import { HospitalDemoTransformer } from '../types';

type TransformerData = { transformer: HospitalDemoTransformer };
type UtilityData = { voltage: number | null; status: 'normal' | 'low' | 'unknown' };
type ZoneData = { zone: string; energized: boolean | null; transformerId: string };

function UtilityNode({ data }: NodeProps<UtilityData>) {
  const status = data.status === 'normal' ? 'stable' : data.status === 'low' ? 'low input' : 'unknown';
  return <div className="hospital-flow-card utility-card" aria-label={`Virtual utility source, ${status}`}>
    <div className="hospital-flow-card-icon"><span className="hospital-flow-source-mark">U</span></div>
    <div className="hospital-flow-card-copy"><span className="hospital-flow-kicker">UPSTREAM SUPPLY</span><strong>Virtual utility source</strong><small>{data.voltage == null ? 'Input reading unavailable' : `Observed input ${data.voltage.toFixed(0)} V`}</small></div>
    <span className={`hospital-flow-state state-${data.status}`}>{status}</span>
    <Handle type="source" position={Position.Bottom} />
  </div>;
}

function TransformerNode({ data }: NodeProps<TransformerData>) {
  const { transformer } = data;
  const { sensors } = transformer;
  const severity = transformer.diagnosis.severity;
  const readings: [string, string][] = [
    ['Current', sensors.current_a == null ? '—' : `${sensors.current_a.toFixed(1)} A`],
    ['Temperature', sensors.temperature_c == null ? '—' : `${sensors.temperature_c.toFixed(1)} °C`],
    ['Input', sensors.input_voltage_v == null ? '—' : `${sensors.input_voltage_v.toFixed(0)} V`],
    ['Output', sensors.output_voltage_v == null ? '—' : `${sensors.output_voltage_v.toFixed(0)} V`],
  ];
  return <div className={`hospital-flow-card transformer-card severity-${severity}`} aria-label={`${transformer.name}, ${transformer.diagnosis.code.replace(/_/g, ' ')}`}>
    <Handle type="target" position={Position.Top} />
    <div className="hospital-transformer-card-heading"><span className="hospital-transformer-symbol"><span /></span><div><span className="hospital-flow-kicker">{transformer.zone}</span><strong>{transformer.id}</strong></div><span className={`hospital-mini-badge severity-${severity}`}>{transformer.diagnosis.code.replace(/_/g, ' ')}</span></div>
    <div className="hospital-flow-readings">{readings.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <div className="hospital-flow-footer"><span>Cooling</span><strong>{sensors.cooling_ok == null ? 'Unknown' : sensors.cooling_ok ? 'Operating' : 'Failed'}</strong><span>Rating</span><strong>{transformer.rated_current_a.toFixed(0)} A</strong></div>
    <Handle type="source" position={Position.Bottom} />
  </div>;
}

function ZoneNode({ data }: NodeProps<ZoneData>) {
  const state = data.energized === true ? 'energized' : data.energized === false ? 'off' : 'unknown';
  return <div className={`hospital-flow-card zone-card state-${state}`} aria-label={`${data.zone}, ${state}`}>
    <Handle type="target" position={Position.Top} />
    <div className="hospital-zone-symbol"><span /></div><div><span className="hospital-flow-kicker">HOSPITAL ZONE</span><strong>{data.zone}</strong><small>{state === 'energized' ? 'Output voltage present' : state === 'off' ? 'Output not energized' : 'Output reading unknown'}</small></div>
  </div>;
}

const nodeTypes = { utility: UtilityNode, transformer: TransformerNode, zone: ZoneNode };
export default function HospitalTopologyGraph({ transformers, stale }: { transformers: HospitalDemoTransformer[]; stale: boolean }) {
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 760);
  useEffect(() => {
    const update = () => setNarrow(window.innerWidth < 760);
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const nodes = useMemo<Node[]>(() => {
    const inputs = transformers.map((item) => item.sensors.input_voltage_v).filter((value): value is number => value != null);
    const voltage = inputs.length ? inputs.reduce((sum, value) => sum + value, 0) / inputs.length : null;
    const utilityStatus: UtilityData['status'] = voltage == null ? 'unknown' : inputs.some((value) => value < 180) ? 'low' : 'normal';
    const utility: Node<UtilityData> = {
      id: 'utility', type: 'utility', position: { x: narrow ? 37 : 413, y: 20 },
      width: 260, height: 110, ariaLabel: 'Virtual upstream utility supply', draggable: false, selectable: false, focusable: true,
      style: { width: 260, height: 110, padding: 0, border: 0, background: 'transparent' },
      data: { voltage, status: utilityStatus },
    };
    const transformerNodes: Node<TransformerData>[] = transformers.map((transformer, index) => ({
      id: transformer.id, type: 'transformer',
      position: narrow ? { x: 32, y: 145 + index * 340 } : { x: 18 + index * 390, y: 176 },
      width: 270, height: 190, ariaLabel: `${transformer.name}, ${transformer.diagnosis.code.replace(/_/g, ' ')}`,
      draggable: false, selectable: false, focusable: true,
      style: { width: 270, height: 190, padding: 0, border: 0, background: 'transparent' },
      data: { transformer },
    }));
    const zoneNodes: Node<ZoneData>[] = transformers.map((transformer, index) => ({
      id: `zone-${transformer.id}`, type: 'zone',
      position: narrow ? { x: 53, y: 355 + index * 340 } : { x: 61 + index * 390, y: 440 },
      width: 184, height: 84, ariaLabel: `${transformer.zone} hospital zone`, draggable: false, selectable: false, focusable: true,
      style: { width: 184, height: 84, padding: 0, border: 0, background: 'transparent' },
      data: { zone: transformer.zone, energized: transformer.energized && transformer.sensors.output_voltage_v != null
        ? transformer.sensors.output_voltage_v >= 100 : transformer.sensors.output_voltage_v == null ? null : false,
        transformerId: transformer.id },
    }));
    return [utility, ...transformerNodes, ...zoneNodes];
  }, [narrow, transformers]);

  const edges = useMemo<Edge[]>(() => transformers.flatMap((transformer) => {
    const input = transformer.sensors.input_voltage_v;
    const output = transformer.sensors.output_voltage_v;
    const inputState = input == null ? 'unknown' : input >= 180 ? 'active' : 'inactive';
    const outputState = output == null ? 'unknown' : transformer.energized && output >= 100 ? 'active' : 'inactive';
    return [
      { id: `supply-${transformer.id}`, source: 'utility', target: transformer.id, type: 'smoothstep', label: input == null ? 'Input unknown' : `${input.toFixed(0)} V input`, animated: inputState === 'active' && !stale, className: `hospital-edge edge-${inputState}`, markerEnd: { type: MarkerType.ArrowClosed, color: inputState === 'active' ? 'var(--status-ok)' : inputState === 'inactive' ? 'var(--text-muted)' : 'var(--status-warn)' }, labelStyle: { fill: 'var(--text-muted)', fontSize: 10, fontWeight: 600 }, labelBgStyle: { fill: 'var(--surface-color)', fillOpacity: 0.96 } },
      { id: `output-${transformer.id}`, source: transformer.id, target: `zone-${transformer.id}`, type: 'smoothstep', label: output == null ? 'Output unknown' : `${output.toFixed(0)} V output`, animated: outputState === 'active' && !stale, className: `hospital-edge edge-${outputState}`, markerEnd: { type: MarkerType.ArrowClosed, color: outputState === 'active' ? 'var(--status-ok)' : outputState === 'inactive' ? 'var(--text-muted)' : 'var(--status-warn)' }, labelStyle: { fill: 'var(--text-muted)', fontSize: 10, fontWeight: 600 }, labelBgStyle: { fill: 'var(--surface-color)', fillOpacity: 0.96 } },
    ];
  }), [stale, transformers]);

  const height = narrow ? 1180 : 590;
  return <div className={`hospital-flow-canvas ${narrow ? 'is-narrow' : ''}`} style={{ height }} role="region" aria-label="Electrical path from utility source through three transformers to hospital zones. Sensor readings determine energized paths.">
    <ReactFlow key={narrow ? 'narrow' : 'wide'} nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.08, minZoom: narrow ? 0.55 : 0.45, maxZoom: 0.95 }} minZoom={0.4} maxZoom={1.1} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} proOptions={{ hideAttribution: true }}>
      <Background color="var(--grid-line)" gap={20} size={1} />
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
  </div>;
}
