import { useMemo, useState } from 'react';
import { ImageViewer } from './ImageViewer';
import './image-viewer.css';

export function ImageViewerDemo({ images }) {
  const [viewerIndex, setViewerIndex] = useState(null);

  const features = useMemo(
    () => [
      '双击缩略图打开查看器，支持 ESC 关闭。',
      '左右方向键切图，切换时重置缩放、偏移与旋转状态。',
      '滚轮按鼠标位置缩放；长图默认适配宽度时优先滚动内容。',
      '放大后支持全方向拖拽，边界硬限制且不露出空白。',
      '提供放大、缩小、1:1、适应窗口、左右旋转、全屏按钮。',
      '窗口尺寸变化时，适应窗口模式会实时重算；放大模式只更新边界。',
      '预加载当前图及前后各一张，并支持缩略图到高清图渐进切换。',
      '支持 GIF 标识位与二维码识别菜单入口，不依赖读取图片实际内容。',
    ],
    [],
  );

  return (
    <div className="viewer-demo">
      <header className="viewer-demo__hero">
        <p className="viewer-demo__eyebrow">Zoom Image Tool</p>
      </header>

      <section className="viewer-demo__section">
        <div className="viewer-demo__section-head">
          <h2>聊天图片列表</h2>
          <span>双击缩略图或点击打开</span>
        </div>

        <div className="viewer-demo__grid">
          {images.map((image, index) => (
            <article key={image.alt} className="viewer-demo__card">
              <button
                type="button"
                className="viewer-demo__thumb"
                onDoubleClick={() => setViewerIndex(index)}
              >
                <img src={image.src} alt={image.alt} loading="lazy" />
                <span className="viewer-demo__thumb-hint">双击打开查看器</span>
                {image.isGif ? <span className="viewer-demo__media-tag">GIF</span> : null}
              </button>

              <div className="viewer-demo__card-body">
                <div>
                  <h3>{image.alt}</h3>
                  <p>{image.description}</p>
                </div>

                <div className="viewer-demo__card-actions">
                  <button type="button" onClick={() => setViewerIndex(index)}>
                    打开查看器
                  </button>
                  {image.hasQr ? <span>含二维码菜单</span> : <span>普通图片</span>}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="viewer-demo__section viewer-demo__section--features">
        <div className="viewer-demo__section-head">
          <h2>实现覆盖点</h2>
          <span>对应 `agents.md` 的交互需求</span>
        </div>

        <ul className="viewer-demo__feature-list">
          {features.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      </section>

      {viewerIndex !== null ? (
        <ImageViewer
          images={images}
          initialIndex={viewerIndex}
          onClose={() => setViewerIndex(null)}
        />
      ) : null}
    </div>
  );
}
