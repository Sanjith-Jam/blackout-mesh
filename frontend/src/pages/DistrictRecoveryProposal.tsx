import type { DistrictProposal } from '../types';

const watts = (value: number | null | undefined) => typeof value === 'number' ? `${value.toLocaleString()} W` : 'Unknown';
const ties = (ids: string[] | null | undefined) => ids?.length ? ids.join(', ') : 'no ties closed';

export default function DistrictRecoveryProposal({ proposal, stale }: { proposal: DistrictProposal | null | undefined; stale: boolean }) {
  if (!proposal) return null;
  const ac = proposal.ac;
  const objectiveRow = (label: string, value: DistrictProposal['objective']) => <tr><th>{label}</th><td>{watts(value?.critical_served_w)}</td><td>{watts(value?.served_w)}</td><td>{value?.switching_actions ?? 'Unknown'}</td></tr>;
  return <section className="district-risk-card" aria-label="Recovery proposal explanation">
    <h3>Proposal · {proposal.solver_status}{stale ? ' · stale' : ''}</h3>
    <p>{proposal.objective_definition}. Loads: {proposal.load_semantics}. Evaluated {proposal.configs_evaluated} of {proposal.configs_total} declared tie configurations{proposal.truncated ? ' (truncated; optimality not claimed)' : ''}. Proposed at revision {proposal.proposed_revision}; inputs digest {proposal.digest.slice(0, 12)}.</p>
    <div className="district-data-table"><table><caption>Objective components</caption><thead><tr><th>Configuration</th><th>Critical served</th><th>Served</th><th>Switching actions</th></tr></thead>
      <tbody>{objectiveRow('Current switches', proposal.baseline_objective)}{objectiveRow('Watt-relaxation bound', proposal.bound_objective)}{objectiveRow(`Validated: ${ties(proposal.candidate_edge_ids)}`, proposal.objective)}</tbody></table></div>
    {proposal.switching_sequence.length > 0 && <p>Break-before-make sequence: {proposal.switching_sequence.map(step => `${step.operation} ${step.edge_id}`).join(' → ')}.</p>}
    {ac && <p>AC check ({ac.engine} {ac.engine_version || ''}, {ac.model}): {ac.status}. Minimum voltage {ac.min_voltage_pu?.toFixed(4) ?? 'Unknown'} pu; maximum line loading {ac.max_line_loading == null ? 'Unknown' : `${(ac.max_line_loading * 100).toFixed(1)}%`}; maximum transformer loading {ac.max_transformer_loading == null ? 'Unknown' : `${(ac.max_transformer_loading * 100).toFixed(1)}%`}; source {ac.source_p_w?.toFixed(1) ?? 'Unknown'} W including {ac.loss_w?.toFixed(2) ?? 'Unknown'} W losses; balance residual {ac.balance_residual_w?.toFixed(4) ?? 'Unknown'} W.</p>}
    {proposal.evaluations.filter(row => row.ac_status !== 'PASSED').map(row => <p key={row.rank} className="district-alert">Rejected rank {row.rank} ({ties(row.edge_ids)}, {watts(row.objective.critical_served_w)} critical): {row.ac_status}. {row.ac_reason} {row.violations.map(v => `${v.limit} at ${v.component_id}: ${v.value} vs ${v.limit_value} ${v.unit}`).join('; ')}</p>)}
    {proposal.refused_configs.map(row => <p key={row.edge_ids.join()}>Not permitted ({ties(row.edge_ids)}): {row.reason}.</p>)}
    <p>Not modeled: {(ac?.unmodeled_checks || ['protection coordination', 'inrush', 'transient/dynamic stability', 'physical switch interlocks']).join(', ')}. Validated means the declared simulation checks passed with synthetic parameters; it is not an operational safety approval.</p>
  </section>;
}
