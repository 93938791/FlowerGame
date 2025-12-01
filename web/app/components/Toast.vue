<template>
  <Transition name="toast">
    <div v-if="show" class="toast" :class="type">
      <span class="toast-icon">{{ icon }}</span>
      <span class="toast-message">{{ message }}</span>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  show: boolean
  message: string
  type: 'success' | 'error' | 'info'
}>()

const icon = computed(() => {
  switch (props.type) {
    case 'success': return '✓'
    case 'error': return '✗'
    default: return 'ℹ'
  }
})
</script>

<style scoped>
.toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
  padding: 16px 24px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  font-size: 15px;
  font-weight: 500;
  min-width: 300px;
  max-width: 500px;
}

.toast.success {
  background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
  color: white;
}

.toast.error {
  background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
  color: white;
}

.toast.info {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
}

.toast-icon {
  font-size: 20px;
  font-weight: bold;
}

.toast-message {
  flex: 1;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}
</style>
