"use client";
import { useState, useCallback, useRef, useEffect } from "react";

const SNAP = 20;
const snap = (v: number) => Math.round(v / SNAP) * SNAP;

export interface CardRect {
  x: number; y: number; w: number; h: number;
  dockSide?: "left" | "right" | null;
}

function storageKey(id: string) { return `grid-card-v2-${id}`; }

function loadRect(id: string, def: CardRect): CardRect {
  if (typeof window === "undefined") return def;
  try {
    const raw = localStorage.getItem(storageKey(id));
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return def;
}

function saveRect(id: string, rect: CardRect) {
  try { localStorage.setItem(storageKey(id), JSON.stringify(rect)); } catch { /* ignore */ }
}

interface DragState  { startMX: number; startMY: number; startX: number; startY: number }
interface ResizeState { startMX: number; startMY: number; startW: number; startH: number }

export function useDragResize(id: string, defaultRect: CardRect, canvasW?: number) {
  const [rect, setRect] = useState<CardRect>(() => loadRect(id, defaultRect));
  const [dragging, setDragging] = useState(false);
  const rectRef = useRef(rect);
  rectRef.current = rect;
  const canvasWRef = useRef(canvasW ?? 0);
  useEffect(() => { canvasWRef.current = canvasW ?? 0; }, [canvasW]);

  const drag   = useRef<DragState | null>(null);
  const resize = useRef<ResizeState | null>(null);

  const onDragDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as Element).setPointerCapture(e.pointerId);
    drag.current = { startMX: e.clientX, startMY: e.clientY, startX: rectRef.current.x, startY: rectRef.current.y };
    setDragging(true);
  }, []);

  const onDragMove = useCallback((e: React.PointerEvent) => {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.startMX;
    const dy = e.clientY - drag.current.startMY;
    setRect(r => ({ ...r, x: Math.max(0, drag.current!.startX + dx), y: Math.max(0, drag.current!.startY + dy) }));
  }, []);

  const onDragUp = useCallback((_e: React.PointerEvent) => {
    if (!drag.current) return;
    drag.current = null;
    setDragging(false);
    setRect(r => {
      let snapped: CardRect = { ...r, x: snap(r.x), y: snap(r.y) };
      let dockSide: "left" | "right" | null = null;
      if (snapped.x === 0) {
        dockSide = "left";
      } else if (canvasWRef.current > 0 && snapped.x + snapped.w >= canvasWRef.current - SNAP) {
        snapped = { ...snapped, x: Math.max(0, canvasWRef.current - snapped.w) };
        dockSide = "right";
      }
      const final = { ...snapped, dockSide };
      saveRect(id, final);
      return final;
    });
  }, [id]);

  const onResizeDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    (e.target as Element).setPointerCapture(e.pointerId);
    resize.current = { startMX: e.clientX, startMY: e.clientY, startW: rectRef.current.w, startH: rectRef.current.h };
  }, []);

  const onResizeMove = useCallback((e: React.PointerEvent) => {
    if (!resize.current) return;
    const dw = e.clientX - resize.current.startMX;
    const dh = e.clientY - resize.current.startMY;
    setRect(r => ({ ...r, w: Math.max(220, resize.current!.startW + dw), h: Math.max(80, resize.current!.startH + dh) }));
  }, []);

  const onResizeUp = useCallback((_e: React.PointerEvent) => {
    if (!resize.current) return;
    resize.current = null;
    setRect(r => {
      const snapped = { ...r, w: snap(r.w), h: snap(r.h) };
      saveRect(id, snapped);
      return snapped;
    });
  }, [id]);

  const resetRect = useCallback(() => {
    saveRect(id, defaultRect);
    setRect(defaultRect);
  }, [id, defaultRect]);

  const undock = useCallback(() => {
    setRect(r => {
      const updated = { ...r, x: 200, dockSide: null };
      saveRect(id, updated);
      return updated;
    });
  }, [id]);

  return {
    rect,
    dragging,
    dragProps:   { onPointerDown: onDragDown,   onPointerMove: onDragMove,   onPointerUp: onDragUp   },
    resizeProps: { onPointerDown: onResizeDown, onPointerMove: onResizeMove, onPointerUp: onResizeUp },
    resetRect,
    undock,
  };
}
