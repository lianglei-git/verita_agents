import img1 from './assets/1.jpg';
import img2 from './assets/2.jpeg';
import img3 from './assets/3.jpeg';
import img4 from './assets/4.jpeg';
import { ImageViewerDemo } from './components/ImageViewerDemo';
import './App.css';

const IMAGES = [
  {
    src: img1,
    hdSrc: img1,
    alt: '图片 1',
    description: '默认图像，支持滚轮缩放与拖拽边界限制。',
  },
  {
    src: img2,
    hdSrc: img2,
    alt: '图片 2',
    description: '示例中启用了二维码识别菜单入口。',
    hasQr: true,
  },
  {
    src: img3,
    hdSrc: img3,
    alt: '图片 3',
    description: '用于验证切图时缩放和偏移重置。',
  },
  {
    src: img4,
    hdSrc: img4,
    alt: '图片 4',
    description: '用于验证旋转、全屏与适应窗口模式。',
  },
];

function App() {
  return (
    <div className="app-root">
      <ImageViewerDemo images={IMAGES} />
    </div>
  );
}

export default App;
