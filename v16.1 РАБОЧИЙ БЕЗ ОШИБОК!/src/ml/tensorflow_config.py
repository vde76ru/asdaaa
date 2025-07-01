"""
Конфигурация TensorFlow для подавления предупреждений
Файл: src/ml/tensorflow_config.py
"""
import os
import warnings

# Подавляем предупреждения перед импортом TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Отключаем GPU если не нужен

# Подавляем предупреждения absl
import absl.logging
absl.logging.set_verbosity(absl.logging.ERROR)

# Подавляем общие предупреждения
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='All log messages before absl::InitializeLog')

# Импортируем TensorFlow с подавленными предупреждениями
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')
    
    # Отключаем eager execution для совместимости
    tf.compat.v1.disable_eager_execution()
    
    # Настройка GPU
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
        except RuntimeError as e:
            print(f"GPU configuration error: {e}")
            
except ImportError:
    tf = None
    print("⚠️ TensorFlow не установлен")

# Функция для безопасного импорта TensorFlow в других модулях
def get_tensorflow():
    """Возвращает настроенный TensorFlow или None"""
    return tf