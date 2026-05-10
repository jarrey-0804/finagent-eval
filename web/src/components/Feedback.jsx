import React from 'react';
import { message, notification, Modal } from 'antd';

/**
 * 统一反馈提示
 */
export const showSuccess = (content = '操作成功') => {
  message.success(content);
};

export const showError = (content = '操作失败') => {
  message.error(content);
};

export const showWarning = (content = '请注意') => {
  message.warning(content);
};

export const showInfo = (content = '提示') => {
  message.info(content);
};

/**
 * 操作确认对话框
 */
export const confirmAction = ({ title, content, onOk, onCancel, okText = '确认', cancelText = '取消', okType = 'primary' }) => {
  Modal.confirm({
    title,
    content,
    okText,
    cancelText,
    okType,
    onOk,
    onCancel,
  });
};

/**
 * 操作成功后的反馈
 */
export const showActionSuccess = (action, target) => {
  notification.success({
    message: `${action}成功`,
    description: `${target}已${action === '删除' ? '删除' : action === '创建' ? '创建' : action}`,
    placement: 'topRight',
    duration: 3,
  });
};

/**
 * 带操作反馈的异步函数包装
 */
export const withFeedback = async (asyncFn, { successMsg, errorMsg, loadingMsg }) => {
  if (loadingMsg) message.loading(loadingMsg);
  try {
    const result = await asyncFn();
    if (successMsg) showSuccess(successMsg);
    return result;
  } catch (error) {
    showError(errorMsg || error?.message || '操作失败');
    throw error;
  }
};

export default { showSuccess, showError, showWarning, showInfo, confirmAction, showActionSuccess, withFeedback };
