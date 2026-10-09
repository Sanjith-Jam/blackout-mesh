import ReactECharts from 'echarts-for-react';

interface ChartProps {
  data: { time: string; servedCount: number; shedCount: number }[];
}

export default function AllocationHistoryChart({ data }: ChartProps) {
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Served', 'Shed'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.map(d => d.time),
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: 'Served',
        type: 'bar',
        stack: 'total',
        data: data.map(d => d.servedCount),
        itemStyle: { color: '#10b981' },
      },
      {
        name: 'Shed',
        type: 'bar',
        stack: 'total',
        data: data.map(d => d.shedCount),
        itemStyle: { color: '#f59e0b' },
      }
    ]
  };

  return <ReactECharts option={option} style={{ height: '300px', width: '100%' }} />;
}
