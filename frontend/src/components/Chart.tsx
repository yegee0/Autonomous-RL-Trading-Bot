import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import type { BacktestMarker, Candle, LiveKline } from "../lib/types";

interface Props {
  candles: Candle[];
  live?: LiveKline | null;
  markers?: BacktestMarker[];
}

export function Chart({ candles, live, markers = [] }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "#0A0A0A" },
        textColor: "#A1A1AA",
        fontFamily: "'Inter', sans-serif",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#161616" },
        horzLines: { color: "#161616" },
      },
      rightPriceScale: { borderColor: "#1F1F1F" },
      timeScale: { borderColor: "#1F1F1F", rightOffset: 4, barSpacing: 8 },
      crosshair: {
        mode: 1,
        vertLine: { color: "#2A2A2A", width: 1, style: 2 },
        horzLine: { color: "#2A2A2A", width: 1, style: 2 },
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#4ADE80",
      downColor: "#F43F5E",
      borderUpColor: "#4ADE80",
      borderDownColor: "#F43F5E",
      wickUpColor: "#4ADE80",
      wickDownColor: "#F43F5E",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: "#2A2A2A",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;
    seriesRef.current = candleSeries;
    volumeRef.current = volumeSeries;
    markersRef.current = createSeriesMarkers(candleSeries, []);

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!markersRef.current) return;
    const data: SeriesMarker<Time>[] = markers.map((m) => ({
      time: m.time as Time,
      position: m.kind === "buy" ? "belowBar" : "aboveBar",
      color: m.kind === "buy" ? "#4ADE80" : "#F43F5E",
      shape: m.kind === "buy" ? "arrowUp" : "arrowDown",
      size: 1,
    }));
    markersRef.current.setMarkers(data);
  }, [markers]);

  useEffect(() => {
    if (!seriesRef.current || !volumeRef.current) return;
    const data: CandlestickData<Time>[] = candles.map((c) => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    const vol: HistogramData<Time>[] = candles.map((c) => ({
      time: c.time as Time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(74, 222, 128, 0.35)" : "rgba(244, 63, 94, 0.35)",
    }));
    seriesRef.current.setData(data);
    volumeRef.current.setData(vol);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  useEffect(() => {
    if (!live || !seriesRef.current) return;
    seriesRef.current.update({
      time: live.time as Time,
      open: live.open,
      high: live.high,
      low: live.low,
      close: live.close,
    });
    volumeRef.current?.update({
      time: live.time as Time,
      value: live.volume,
      color: live.close >= live.open ? "rgba(74, 222, 128, 0.35)" : "rgba(244, 63, 94, 0.35)",
    });
  }, [live]);

  return <div ref={containerRef} className="h-full w-full" />;
}
