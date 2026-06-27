import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

const ZOOM_FACTOR = 1.12;
const EPSILON = 0.001;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeRotation(value) {
  return ((value % 360) + 360) % 360;
}

function getBounds(renderedWidth, renderedHeight, containerWidth, containerHeight) {
  return {
    maxX: Math.max((renderedWidth - containerWidth) / 2, 0),
    maxY: Math.max((renderedHeight - containerHeight) / 2, 0),
  };
}

function clampOffset(offset, renderedWidth, renderedHeight, containerWidth, containerHeight) {
  const bounds = getBounds(renderedWidth, renderedHeight, containerWidth, containerHeight);

  return {
    x: clamp(offset.x, -bounds.maxX, bounds.maxX),
    y: clamp(offset.y, -bounds.maxY, bounds.maxY),
  };
}

function getFitScale(mediaWidth, mediaHeight, containerWidth, containerHeight, isLongImage) {
  if (!mediaWidth || !mediaHeight || !containerWidth || !containerHeight) {
    return 1;
  }

  if (isLongImage) {
    return Math.min(containerWidth / mediaWidth, 1);
  }

  return Math.min(containerWidth / mediaWidth, containerHeight / mediaHeight, 1);
}

function getDefaultFitOffset(
  renderedWidth,
  renderedHeight,
  containerWidth,
  containerHeight,
  isLongImage,
) {
  const bounds = getBounds(renderedWidth, renderedHeight, containerWidth, containerHeight);

  return {
    x: 0,
    y: isLongImage && bounds.maxY > 0 ? bounds.maxY : 0,
  };
}

function isAlmostEqual(a, b) {
  return Math.abs(a - b) < EPSILON;
}

export function ImageViewer({ images, initialIndex, onClose }) {
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [rotation, setRotation] = useState(0);
  const [viewMode, setViewMode] = useState('fit');
  const [fitOffsetOverride, setFitOffsetOverride] = useState(null);
  const [freeScale, setFreeScale] = useState(1);
  const [freeOffset, setFreeOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [dimensions, setDimensions] = useState(() => images.map(() => ({ width: 0, height: 0 })));
  const [loadedHd, setLoadedHd] = useState({});
  const [menu, setMenu] = useState(null);
  const [toast, setToast] = useState('');

  const viewerRef = useRef(null);
  const stageRef = useRef(null);
  const dragStateRef = useRef(null);
  const preloadRef = useRef(new Map());
  const toastTimerRef = useRef(null);

  const showToast = useCallback((nextToast) => {
    window.clearTimeout(toastTimerRef.current);
    setToast(nextToast);
    toastTimerRef.current = window.setTimeout(() => setToast(''), 1800);
  }, []);

  useEffect(() => {
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = '';
      window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  useLayoutEffect(() => {
    if (!stageRef.current) {
      return undefined;
    }

    const node = stageRef.current;
    const updateSize = () => {
      const rect = node.getBoundingClientRect();
      setContainerSize({
        width: rect.width,
        height: rect.height,
      });
    };

    updateSize();

    const observer = new ResizeObserver(updateSize);
    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === viewerRef.current);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  useEffect(() => {
    if (!menu) {
      return undefined;
    }

    const closeMenu = () => setMenu(null);
    window.addEventListener('click', closeMenu);

    return () => window.removeEventListener('click', closeMenu);
  }, [menu]);

  const currentImage = images[activeIndex];
  const currentDimensions = dimensions[activeIndex] ?? { width: 0, height: 0 };
  const normalizedRotation = normalizeRotation(rotation);
  const isQuarterTurn = normalizedRotation % 180 !== 0;
  const mediaWidth = isQuarterTurn ? currentDimensions.height : currentDimensions.width;
  const mediaHeight = isQuarterTurn ? currentDimensions.width : currentDimensions.height;
  const tentativeLongScale =
    mediaWidth && containerSize.width ? Math.min(containerSize.width / mediaWidth, 1) : 1;
  const isLongImage =
    mediaWidth > 0 &&
    mediaHeight / Math.max(mediaWidth, 1) >= 1.8 &&
    mediaHeight * tentativeLongScale > containerSize.height;
  const fitScale = getFitScale(
    mediaWidth,
    mediaHeight,
    containerSize.width,
    containerSize.height,
    isLongImage,
  );
  const fitRenderedWidth = mediaWidth * fitScale;
  const fitRenderedHeight = mediaHeight * fitScale;
  const defaultFitOffset = useMemo(
    () =>
      getDefaultFitOffset(
        fitRenderedWidth,
        fitRenderedHeight,
        containerSize.width,
        containerSize.height,
        isLongImage,
      ),
    [
      containerSize.height,
      containerSize.width,
      fitRenderedHeight,
      fitRenderedWidth,
      isLongImage,
    ],
  );
  const maxScale = Math.max(
    fitScale,
    Math.min(10, 6400 / Math.max(mediaWidth || 1, mediaHeight || 1)),
  );
  const scale =
    viewMode === 'fit' ? fitScale : clamp(freeScale || fitScale, fitScale, maxScale);
  const renderedWidth = mediaWidth * scale;
  const renderedHeight = mediaHeight * scale;
  const bounds = useMemo(
    () =>
      getBounds(renderedWidth, renderedHeight, containerSize.width, containerSize.height),
    [containerSize.height, containerSize.width, renderedHeight, renderedWidth],
  );
  const resolvedFitOffset = clampOffset(
    fitOffsetOverride ?? defaultFitOffset,
    fitRenderedWidth,
    fitRenderedHeight,
    containerSize.width,
    containerSize.height,
  );
  const resolvedFreeOffset = clampOffset(
    freeOffset,
    renderedWidth,
    renderedHeight,
    containerSize.width,
    containerSize.height,
  );
  const offset = viewMode === 'fit' ? resolvedFitOffset : resolvedFreeOffset;
  const canPan = viewMode === 'free' && (bounds.maxX > 0.5 || bounds.maxY > 0.5);
  const canZoomIn = scale < maxScale - EPSILON;
  const canZoomOut = scale > fitScale + EPSILON;
  const canGoPrev = activeIndex > 0;
  const canGoNext = activeIndex < images.length - 1;
  const isGif =
    currentImage?.isGif || /\.gif(?:$|\?)/i.test(currentImage?.hdSrc || currentImage?.src);
  const hdSrc = currentImage?.hdSrc || currentImage?.src;
  const displaySrc = loadedHd[hdSrc] ? hdSrc : currentImage?.src;
  const hdLoading = Boolean(hdSrc && hdSrc !== currentImage?.src && !loadedHd[hdSrc]);

  const resetToFit = useCallback(() => {
    setViewMode('fit');
    setFitOffsetOverride(null);
    setFreeScale(1);
    setFreeOffset({ x: 0, y: 0 });
    setDragging(false);
    dragStateRef.current = null;
  }, []);

  useEffect(() => {
    if (!currentImage) {
      return;
    }

    const indicesToPreload = [activeIndex - 1, activeIndex, activeIndex + 1].filter(
      (index) => index >= 0 && index < images.length,
    );

    indicesToPreload.forEach((index) => {
      const image = images[index];
      const hdSrc = image.hdSrc || image.src;

      if (!hdSrc || loadedHd[hdSrc] || preloadRef.current.has(hdSrc)) {
        return;
      }

      const preloader = new Image();
      preloadRef.current.set(hdSrc, preloader);

      preloader.onload = () => {
        preloadRef.current.delete(hdSrc);
        setLoadedHd((prev) => (prev[hdSrc] ? prev : { ...prev, [hdSrc]: true }));
      };

      preloader.onerror = () => {
        preloadRef.current.delete(hdSrc);
      };

      preloader.src = hdSrc;
    });
  }, [activeIndex, currentImage, images, loadedHd]);

  const goToIndex = useCallback(
    (nextIndex) => {
      if (nextIndex < 0 || nextIndex >= images.length) {
        return;
      }

      setActiveIndex(nextIndex);
      setRotation(0);
      resetToFit();
      setMenu(null);
    },
    [images.length, resetToFit],
  );

  const zoomAroundPoint = useCallback(
    (direction, anchorPoint) => {
      if (!mediaWidth || !mediaHeight || !containerSize.width || !containerSize.height) {
        return;
      }

      const multiplier = direction > 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR;
      const nextScale = clamp(scale * multiplier, fitScale, maxScale);

      if (isAlmostEqual(nextScale, scale)) {
        return;
      }

      if (isAlmostEqual(nextScale, fitScale)) {
        resetToFit();
        return;
      }

      const localX = (anchorPoint.x - offset.x) / scale;
      const localY = (anchorPoint.y - offset.y) / scale;

      const nextOffset = clampOffset(
        {
          x: anchorPoint.x - localX * nextScale,
          y: anchorPoint.y - localY * nextScale,
        },
        mediaWidth * nextScale,
        mediaHeight * nextScale,
        containerSize.width,
        containerSize.height,
      );

      setViewMode('free');
      setFreeScale(nextScale);
      setFreeOffset(nextOffset);
    },
    [
      containerSize.height,
      containerSize.width,
      fitScale,
      maxScale,
      mediaHeight,
      mediaWidth,
      offset.x,
      offset.y,
      resetToFit,
      scale,
    ],
  );

  const setActualSize = useCallback(() => {
    if (!mediaWidth || !mediaHeight || !containerSize.width || !containerSize.height) {
      return;
    }

    const nextScale = clamp(1, fitScale, maxScale);

    if (isAlmostEqual(nextScale, fitScale)) {
      resetToFit();
      return;
    }

    setViewMode('free');
    setFreeScale(nextScale);
    setFreeOffset(
      clampOffset(
        { x: 0, y: 0 },
        mediaWidth * nextScale,
        mediaHeight * nextScale,
        containerSize.width,
        containerSize.height,
      ),
    );
  }, [
    containerSize.height,
    containerSize.width,
    fitScale,
    maxScale,
    mediaHeight,
    mediaWidth,
    resetToFit,
  ]);

  const toggleFullscreen = useCallback(async () => {
    if (!viewerRef.current) {
      return;
    }

    try {
      if (document.fullscreenElement === viewerRef.current) {
        await document.exitFullscreen();
      } else {
        await viewerRef.current.requestFullscreen();
      }
    } catch {
      showToast('当前环境不支持全屏切换。');
    }
  }, [showToast]);

  const handleWheel = useCallback(
    (event) => {
      event.preventDefault();
      setMenu(null);

      if (!stageRef.current) {
        return;
      }

      const rect = stageRef.current.getBoundingClientRect();
      const anchorPoint = {
        x: event.clientX - rect.left - rect.width / 2,
        y: event.clientY - rect.top - rect.height / 2,
      };
      const longImageCanScroll =
        viewMode === 'fit' &&
        isLongImage &&
        fitRenderedHeight > containerSize.height + 0.5 &&
        fitRenderedWidth <= containerSize.width + 0.5 &&
        !event.ctrlKey;

      if (longImageCanScroll) {
        setFitOffsetOverride((prev) =>
          clampOffset(
            {
              x: 0,
              y: (prev ?? defaultFitOffset).y - event.deltaY,
            },
            fitRenderedWidth,
            fitRenderedHeight,
            containerSize.width,
            containerSize.height,
          ),
        );
        return;
      }

      zoomAroundPoint(event.deltaY < 0 ? 1 : -1, anchorPoint);
    },
    [
      containerSize.height,
      containerSize.width,
      defaultFitOffset,
      fitRenderedHeight,
      fitRenderedWidth,
      isLongImage,
      viewMode,
      zoomAroundPoint,
    ],
  );

  const handleMouseDown = useCallback(
    (event) => {
      if (event.button !== 0 || !canPan) {
        return;
      }

      event.preventDefault();
      setMenu(null);
      setDragging(true);
      dragStateRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        origin: offset,
      };
    },
    [canPan, offset],
  );

  useEffect(() => {
    if (!dragging) {
      return undefined;
    }

    const handleMouseMove = (event) => {
      if (!dragStateRef.current) {
        return;
      }

      const nextOffset = clampOffset(
        {
          x: dragStateRef.current.origin.x + event.clientX - dragStateRef.current.startX,
          y: dragStateRef.current.origin.y + event.clientY - dragStateRef.current.startY,
        },
        renderedWidth,
        renderedHeight,
        containerSize.width,
        containerSize.height,
      );

      setFreeOffset(nextOffset);
    };

    const stopDragging = () => {
      setDragging(false);
      dragStateRef.current = null;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', stopDragging);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', stopDragging);
    };
  }, [
    containerSize.height,
    containerSize.width,
    dragging,
    renderedHeight,
    renderedWidth,
  ]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        goToIndex(activeIndex - 1);
        return;
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault();
        goToIndex(activeIndex + 1);
        return;
      }

      if (event.key === ' ') {
        event.preventDefault();
        resetToFit();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeIndex, goToIndex, onClose, resetToFit]);

  const handleContextMenu = useCallback((event) => {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
    });
  }, []);

  const handleImageLoad = useCallback(
    (event) => {
      const nextDimensions = {
        width: event.currentTarget.naturalWidth,
        height: event.currentTarget.naturalHeight,
      };

      setDimensions((prev) => {
        const current = prev[activeIndex];

        if (
          current &&
          current.width === nextDimensions.width &&
          current.height === nextDimensions.height
        ) {
          return prev;
        }

        const next = [...prev];
        next[activeIndex] = nextDimensions;
        return next;
      });
    },
    [activeIndex],
  );

  const stageCursor = dragging
    ? 'grabbing'
    : canPan
      ? 'grab'
      : viewMode === 'fit' && fitScale < 1 - EPSILON
        ? 'zoom-in'
        : 'default';

  const handleRecognizeQr = useCallback(() => {
    if (currentImage?.hasQr) {
      showToast('已触发二维码识别入口。');
      return;
    }

    showToast('当前图片未标记二维码能力。');
  }, [currentImage, showToast]);

  const infoLabel = isLongImage && viewMode === 'fit' ? '长图滚动模式' : viewMode === 'fit' ? '适应窗口' : '放大模式';

  if (!currentImage) {
    return null;
  }

  return (
    <div
      ref={viewerRef}
      className={`image-viewer ${isFullscreen ? 'is-fullscreen' : ''}`}
      onMouseDown={() => setMenu(null)}
    >
      <div className="image-viewer__backdrop" onClick={onClose} />

      <div className="image-viewer__panel">
        <header className="image-viewer__header">
          <div className="image-viewer__meta">
            <strong>{currentImage.alt}</strong>
            <span>
              {activeIndex + 1} / {images.length}
            </span>
            <span>{Math.round(scale * 100)}%</span>
            <span>{infoLabel}</span>
            {isGif ? <span className="image-viewer__badge">GIF</span> : null}
          </div>

          <div className="image-viewer__header-actions">
            <button type="button" onClick={toggleFullscreen}>
              {isFullscreen ? '退出全屏' : '全屏'}
            </button>
            <button type="button" onClick={onClose}>
              关闭
            </button>
          </div>
        </header>

        <div className="image-viewer__body">
          <button
            type="button"
            className="image-viewer__side image-viewer__side--left"
            onClick={() => goToIndex(activeIndex - 1)}
            disabled={!canGoPrev}
          >
            ←
          </button>

          <div
            ref={stageRef}
            className="image-viewer__stage"
            style={{ cursor: stageCursor }}
            onWheel={handleWheel}
            onDoubleClick={toggleFullscreen}
            onMouseDown={handleMouseDown}
            onContextMenu={handleContextMenu}
          >
            <img
              className={`image-viewer__image ${hdLoading ? 'is-loading-hd' : ''} ${
                dragging ? 'is-dragging' : ''
              }`}
              src={displaySrc}
              alt={currentImage.alt}
              draggable={false}
              onLoad={handleImageLoad}
              style={{
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale}) rotate(${rotation}deg)`,
              }}
            />

            {hdLoading ? <div className="image-viewer__loading">高清图加载中...</div> : null}
          </div>

          <button
            type="button"
            className="image-viewer__side image-viewer__side--right"
            onClick={() => goToIndex(activeIndex + 1)}
            disabled={!canGoNext}
          >
            →
          </button>
        </div>

        <footer className="image-viewer__toolbar">
          <button type="button" onClick={() => zoomAroundPoint(1, { x: 0, y: 0 })} disabled={!canZoomIn}>
            +
          </button>
          <button
            type="button"
            onClick={() => zoomAroundPoint(-1, { x: 0, y: 0 })}
            disabled={!canZoomOut}
          >
            -
          </button>
          <button type="button" onClick={setActualSize} disabled={isAlmostEqual(clamp(1, fitScale, maxScale), scale)}>
            1:1
          </button>
          <button
            type="button"
            onClick={resetToFit}
            disabled={
              viewMode === 'fit' &&
              isAlmostEqual(offset.x, defaultFitOffset.x) &&
              isAlmostEqual(offset.y, defaultFitOffset.y) &&
              isAlmostEqual(scale, fitScale)
            }
          >
            适应窗口
          </button>
          <button
            type="button"
            onClick={() => {
              setRotation((prev) => prev - 90);
              resetToFit();
            }}
          >
            左转
          </button>
          <button
            type="button"
            onClick={() => {
              setRotation((prev) => prev + 90);
              resetToFit();
            }}
          >
            右转
          </button>
          <button type="button" onClick={handleRecognizeQr} disabled={!currentImage.hasQr}>
            识别二维码
          </button>
        </footer>
      </div>

      {menu ? (
        <div className="image-viewer__menu" style={{ left: menu.x, top: menu.y }}>
          <button type="button" onClick={() => zoomAroundPoint(1, { x: 0, y: 0 })} disabled={!canZoomIn}>
            放大
          </button>
          <button type="button" onClick={() => zoomAroundPoint(-1, { x: 0, y: 0 })} disabled={!canZoomOut}>
            缩小
          </button>
          <button type="button" onClick={setActualSize}>
            1:1
          </button>
          <button type="button" onClick={resetToFit}>
            适应窗口
          </button>
          <button
            type="button"
            onClick={() => {
              setRotation((prev) => prev - 90);
              resetToFit();
            }}
          >
            向左旋转
          </button>
          <button
            type="button"
            onClick={() => {
              setRotation((prev) => prev + 90);
              resetToFit();
            }}
          >
            向右旋转
          </button>
          <button type="button" onClick={handleRecognizeQr} disabled={!currentImage.hasQr}>
            识别图中二维码
          </button>
        </div>
      ) : null}

      {toast ? <div className="image-viewer__toast">{toast}</div> : null}
    </div>
  );
}
