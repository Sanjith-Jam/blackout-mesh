import ReactECharts from 'echarts-for-react';

interface ChartProps {
  data: { time: string; capacity: number; demand: number }[];
}

export default function SourceCapacityDemandChart({ data }: ChartProps) {
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Capacity (W)', 'Demand (W)'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLabel: { formatter: (value: string) => new Date(value).toLocaleTimeString() },
      data: data.map(d => d.time),
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'Capacity (W)',
        type: 'line',
        step: 'end',
        data: data.map(d => d.capacity),
        itemStyle: { color: '#3b82f6' },
      },
      {
        name: 'Demand (W)',
        type: 'line',
        step: 'end',
        data: data.map(d => d.demand),
        itemStyle: { color: '#ef4444' },
      }
    ]
  };

  return <ReactECharts option={option} style={{ height: '300px', width: '100%' }} />;
}
