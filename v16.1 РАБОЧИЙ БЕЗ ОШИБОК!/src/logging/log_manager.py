"""
Менеджер логов с автоматической очисткой и архивацией
Файл: src/logging/log_manager.py
"""
import os
import gzip
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import json

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from .smart_logger import TradingLog


class LogManager:
    """
    Управляет жизненным циклом логов
    """
    
    def __init__(self, log_dir: Path = Path("logs"), archive_dir: Path = Path("logs/archive")):
        self.log_dir = log_dir
        self.archive_dir = archive_dir
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Настройки хранения
        self.file_retention_days = 7      # Файлы логов
        self.db_retention_days = 30       # Записи в БД
        self.archive_retention_days = 90  # Архивы
        
        # Настройки очистки БД
        self.db_cleanup_batch_size = 1000
        self.important_categories = {'trade', 'profit_loss', 'error', 'signal'}
    
    async def cleanup_logs(self):
        """Основной метод очистки логов"""
        try:
            # Очистка файлов
            self._cleanup_log_files()
            
            # Архивация старых логов
            self._archive_old_logs()
            
            # Очистка БД
            await self._cleanup_database_logs()
            
            # Очистка старых архивов
            self._cleanup_old_archives()
            
            # Создание сводного отчета
            await self._create_summary_report()
            
        except Exception as e:
            print(f"Ошибка очистки логов: {e}")
    
    def _cleanup_log_files(self):
        """Удаляет старые файлы логов"""
        cutoff_date = datetime.now() - timedelta(days=self.file_retention_days)
        
        for log_file in self.log_dir.glob("*.log*"):
            # Пропускаем текущие файлы
            if log_file.suffix == '.log':
                continue
                
            # Проверяем дату модификации
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff_date:
                log_file.unlink()
                print(f"Удален старый лог: {log_file}")
    
    def _archive_old_logs(self):
        """Архивирует логи для долгосрочного хранения"""
        # Архивируем логи старше 1 дня
        cutoff_date = datetime.now() - timedelta(days=1)
        
        for log_file in self.log_dir.glob("*.log.*"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            if mtime < cutoff_date and not log_file.suffix.endswith('.gz'):
                # Создаем имя архива
                archive_name = self.archive_dir / f"{log_file.name}.gz"
                
                # Сжимаем файл
                with open(log_file, 'rb') as f_in:
                    with gzip.open(archive_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Удаляем оригинал
                log_file.unlink()
                print(f"Архивирован лог: {log_file} -> {archive_name}")
    
    def _cleanup_old_archives(self):
        """Удаляет старые архивы"""
        cutoff_date = datetime.now() - timedelta(days=self.archive_retention_days)
        
        for archive_file in self.archive_dir.glob("*.gz"):
            mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
            if mtime < cutoff_date:
                archive_file.unlink()
                print(f"Удален старый архив: {archive_file}")
    
    async def _cleanup_database_logs(self):
        """Очищает старые записи из БД"""
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.db_retention_days)
            
            # Сначала экспортируем важные логи
            important_logs = db.query(TradingLog).filter(
                and_(
                    TradingLog.created_at < cutoff_date,
                    TradingLog.category.in_(self.important_categories)
                )
            ).all()
            
            if important_logs:
                await self._export_important_logs(important_logs)
            
            # Удаляем старые логи батчами
            while True:
                deleted = db.query(TradingLog).filter(
                    TradingLog.created_at < cutoff_date
                ).limit(self.db_cleanup_batch_size).delete(synchronize_session=False)
                
                db.commit()
                
                if deleted < self.db_cleanup_batch_size:
                    break
                
                await asyncio.sleep(0.1)  # Даем БД передышку
            
            print(f"Очищено логов из БД: {deleted}")
            
        except Exception as e:
            db.rollback()
            print(f"Ошибка очистки БД: {e}")
        finally:
            db.close()
    
    async def _export_important_logs(self, logs: List[TradingLog]):
        """Экспортирует важные логи перед удалением"""
        export_file = self.archive_dir / f"important_logs_{datetime.now().strftime('%Y%m%d')}.json"
        
        logs_data = []
        for log in logs:
            logs_data.append({
                'timestamp': log.created_at.isoformat(),
                'level': log.log_level,
                'category': log.category,
                'message': log.message,
                'context': log.context,
                'symbol': log.symbol,
                'strategy': log.strategy,
                'trade_id': log.trade_id,
                'signal_id': log.signal_id
            })
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(logs_data, f, ensure_ascii=False, indent=2)
        
        # Сжимаем
        with open(export_file, 'rb') as f_in:
            with gzip.open(f"{export_file}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        export_file.unlink()
        print(f"Экспортировано важных логов: {len(logs_data)}")
    
    async def _create_summary_report(self):
        """Создает сводный отчет по логам"""
        db = SessionLocal()
        try:
            # Собираем статистику
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            
            # Статистика по категориям
            category_stats = db.query(
                TradingLog.category,
                TradingLog.log_level,
                func.count(TradingLog.id).label('count')
            ).filter(
                TradingLog.created_at >= day_ago
            ).group_by(
                TradingLog.category,
                TradingLog.log_level
            ).all()
            
            # Статистика по ошибкам
            error_stats = db.query(
                TradingLog.symbol,
                TradingLog.strategy,
                func.count(TradingLog.id).label('count')
            ).filter(
                and_(
                    TradingLog.created_at >= day_ago,
                    TradingLog.log_level.in_(['ERROR', 'CRITICAL'])
                )
            ).group_by(
                TradingLog.symbol,
                TradingLog.strategy
            ).all()
            
            # Создаем отчет
            report = {
                'date': now.isoformat(),
                'period': '24h',
                'total_logs': sum(stat.count for stat in category_stats),
                'by_category': {},
                'errors': {
                    'total': sum(stat.count for stat in error_stats),
                    'by_symbol': {},
                    'by_strategy': {}
                }
            }
            
            # Группируем по категориям
            for stat in category_stats:
                if stat.category not in report['by_category']:
                    report['by_category'][stat.category] = {}
                report['by_category'][stat.category][stat.log_level] = stat.count
            
            # Группируем ошибки
            for stat in error_stats:
                if stat.symbol:
                    report['errors']['by_symbol'][stat.symbol] = stat.count
                if stat.strategy:
                    report['errors']['by_strategy'][stat.strategy] = stat.count
            
            # Сохраняем отчет
            report_file = self.log_dir / f"daily_report_{now.strftime('%Y%m%d')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"Создан дневной отчет: {report_file}")
            
        except Exception as e:
            print(f"Ошибка создания отчета: {e}")
        finally:
            db.close()
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Получает статистику по логам"""
        stats = {
            'file_count': 0,
            'total_size_mb': 0,
            'archive_count': 0,
            'archive_size_mb': 0,
            'oldest_log': None,
            'newest_log': None
        }
        
        # Статистика по файлам
        log_files = list(self.log_dir.glob("*.log*"))
        if log_files:
            stats['file_count'] = len(log_files)
            stats['total_size_mb'] = sum(f.stat().st_size for f in log_files) / 1024 / 1024
            
            oldest = min(log_files, key=lambda f: f.stat().st_mtime)
            newest = max(log_files, key=lambda f: f.stat().st_mtime)
            
            stats['oldest_log'] = datetime.fromtimestamp(oldest.stat().st_mtime).isoformat()
            stats['newest_log'] = datetime.fromtimestamp(newest.stat().st_mtime).isoformat()
        
        # Статистика по архивам
        archive_files = list(self.archive_dir.glob("*.gz"))
        if archive_files:
            stats['archive_count'] = len(archive_files)
            stats['archive_size_mb'] = sum(f.stat().st_size for f in archive_files) / 1024 / 1024
        
        return stats


# Создаем планировщик для автоматической очистки
class LogCleanupScheduler:
    """Планировщик очистки логов"""
    
    def __init__(self, log_manager: LogManager):
        self.log_manager = log_manager
        self.running = False
        self._task = None
    
    async def start(self):
        """Запускает планировщик"""
        self.running = True
        self._task = asyncio.create_task(self._run())
    
    async def stop(self):
        """Останавливает планировщик"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run(self):
        """Основной цикл планировщика"""
        while self.running:
            try:
                # Запускаем очистку в 3:00 ночи
                now = datetime.now()
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                wait_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                if self.running:
                    print(f"Запуск очистки логов: {datetime.now()}")
                    await self.log_manager.cleanup_logs()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ошибка в планировщике очистки: {e}")
                await asyncio.sleep(3600)  # Повтор через час при ошибке


# Глобальные экземпляры
log_manager = LogManager()
cleanup_scheduler = LogCleanupScheduler(log_manager)