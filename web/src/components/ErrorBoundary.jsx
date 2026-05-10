import React from 'react';
import { Result, Button } from 'antd';

/**
 * 错误边界组件
 * 捕获子组件树中的 JavaScript 错误，记录错误并显示回退 UI
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // 更新 state 使下一次渲染能够显示回退 UI
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // 记录错误信息
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      // 自定义回退 UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Result
          status="error"
          title="页面出错了"
          subTitle={this.state.error?.message || '发生了未知错误，请刷新页面重试'}
          extra={[
            <Button type="primary" key="reload" onClick={this.handleReload}>
              刷新页面
            </Button>,
            <Button key="reset" onClick={this.handleReset}>
              重试
            </Button>,
          ]}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * 高阶组件：为组件添加错误边界
 */
export const withErrorBoundary = (WrappedComponent, fallback = null) => {
  const WithErrorBoundary = (props) => (
    <ErrorBoundary fallback={fallback}>
      <WrappedComponent {...props} />
    </ErrorBoundary>
  );

  WithErrorBoundary.displayName = `WithErrorBoundary(${WrappedComponent.displayName || WrappedComponent.name || 'Component'})`;

  return WithErrorBoundary;
};

/**
 * 网络错误回退 UI
 */
export const NetworkErrorFallback = ({ onRetry }) => (
  <Result
    status="500"
    title="网络连接失败"
    subTitle="请检查网络连接后重试"
    extra={
      <Button type="primary" onClick={onRetry}>
        重新连接
      </Button>
    }
  />
);

/**
 * 404 错误回退 UI
 */
export const NotFoundFallback = ({ onBack }) => (
  <Result
    status="404"
    title="页面不存在"
    subTitle="您访问的页面不存在或已被删除"
    extra={
      <Button type="primary" onClick={onBack}>
        返回首页
      </Button>
    }
  />
);

/**
 * 权限错误回退 UI
 */
export const ForbiddenFallback = ({ onLogin }) => (
  <Result
    status="403"
    title="无访问权限"
    subTitle="您没有权限访问此页面，请登录后重试"
    extra={
      <Button type="primary" onClick={onLogin}>
        重新登录
      </Button>
    }
  />
);

export default ErrorBoundary;
