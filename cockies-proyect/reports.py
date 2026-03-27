"""
Sistema de generación de reportes de productividad.

Genera reportes formateados para enviar por Telegram con
estadísticas de uso, clasificación de productividad y recomendaciones.
"""
from datetime import datetime


class ReportGenerator:
    """Genera reportes de productividad formateados para Telegram."""

    def generate_periodic_report(self, keyboard_stats: dict, app_stats: dict,
                                  app_classification: dict, browser_summary: dict,
                                  url_classification: dict,
                                  captured_text: dict | None = None) -> str:
        """Genera un reporte periódico (cada 30 min por defecto)."""
        now = datetime.now().strftime("%H:%M")
        score = app_classification.get("productivity_score", 0)
        score_emoji = self._score_emoji(score)

        lines = [
            f"📊 <b>Reporte de Actividad — {now}</b>",
            f"",
            f"{score_emoji} Productividad: <b>{score}%</b>",
            f"",
        ]

        # Estadísticas de apps
        lines.append("💻 <b>Aplicaciones:</b>")
        lines.append(f"  • Tiempo productivo: {app_classification.get('productive_minutes', 0)} min")
        lines.append(f"  • Tiempo improductivo: {app_classification.get('unproductive_minutes', 0)} min")
        lines.append(f"  • Tiempo neutral: {app_classification.get('neutral_minutes', 0)} min")
        lines.append(f"  • Cambios de ventana: {app_stats.get('app_switches', 0)}")

        # Top apps
        top_apps = app_stats.get("top_apps", [])[:5]
        if top_apps:
            lines.append(f"")
            lines.append("🏆 <b>Top Apps:</b>")
            for i, app in enumerate(top_apps, 1):
                lines.append(f"  {i}. {app['app']} — {app['minutes']} min")

        # Navegación
        if browser_summary.get("total_visits", 0) > 0:
            lines.append(f"")
            lines.append("🌐 <b>Navegación:</b>")
            lines.append(f"  • Sitios visitados: {browser_summary.get('total_visits', 0)}")
            lines.append(f"  • Productivos: {url_classification.get('productive_count', 0)}")
            lines.append(f"  • Improductivos: {url_classification.get('unproductive_count', 0)}")

            # Top dominios
            domains = browser_summary.get("domains", {})
            top_domains = list(domains.items())[:5]
            if top_domains:
                lines.append("")
                lines.append("🔗 <b>Top Sitios:</b>")
                for domain, count in top_domains:
                    lines.append(f"  • {domain} ({count})")

        # Teclado
        lines.append(f"")
        lines.append("⌨️ <b>Actividad de Teclado:</b>")
        lines.append(f"  • Total pulsaciones: {keyboard_stats.get('total_keypresses', 0)}")

        # Texto capturado por ventana
        if captured_text:
            lines.append(f"")
            lines.append("📝 <b>Texto escrito por ventana:</b>")
            # Ordenar por largo de texto (más activo primero)
            sorted_windows = sorted(captured_text.items(), key=lambda x: -len(x[1]))
            for window, text in sorted_windows[:8]:
                text = text.strip()
                if not text:
                    continue
                preview = text[-200:] if len(text) > 200 else text
                preview = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                short_win = window[:50]
                lines.append(f"")
                lines.append(f"💻 <b>{short_win}</b>")
                lines.append(f"<code>{preview}</code>")

        return "\n".join(lines)

    def generate_daily_report(self, keyboard_stats: dict, app_stats: dict,
                               app_classification: dict, browser_summary: dict,
                               url_classification: dict,
                               captured_text: dict | None = None) -> str:
        """Genera el reporte diario completo."""
        now = datetime.now().strftime("%Y-%m-%d")
        score = app_classification.get("productivity_score", 0)
        score_emoji = self._score_emoji(score)

        total_minutes = app_stats.get("total_tracked_minutes", 0)
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)

        lines = [
            f"📋 <b>REPORTE DIARIO — {now}</b>",
            f"{'='*30}",
            f"",
            f"{score_emoji} <b>Productividad del día: {score}%</b>",
            f"⏱ Tiempo total rastreado: {hours}h {mins}min",
            f"",
            f"{'─'*30}",
            f"💻 <b>USO DE APLICACIONES</b>",
            f"  ✅ Productivo: {app_classification.get('productive_minutes', 0)} min",
            f"  ❌ Improductivo: {app_classification.get('unproductive_minutes', 0)} min",
            f"  ⚪ Neutral: {app_classification.get('neutral_minutes', 0)} min",
            f"  🔄 Cambios de ventana: {app_stats.get('app_switches', 0)}",
        ]

        # Todas las apps usadas
        top_apps = app_stats.get("top_apps", [])
        if top_apps:
            lines.append(f"")
            lines.append("📱 <b>Aplicaciones usadas:</b>")
            for i, app in enumerate(top_apps, 1):
                lines.append(f"  {i}. {app['app']} — {app['minutes']} min")

        # Navegación completa
        lines.append(f"")
        lines.append(f"{'─'*30}")
        lines.append("🌐 <b>NAVEGACIÓN WEB</b>")
        lines.append(f"  Total de visitas: {browser_summary.get('total_visits', 0)}")
        lines.append(f"  ✅ Productivas: {url_classification.get('productive_count', 0)}")
        lines.append(f"  ❌ Improductivas: {url_classification.get('unproductive_count', 0)}")

        # Top dominios
        domains = browser_summary.get("domains", {})
        if domains:
            lines.append("")
            lines.append("🔗 <b>Todos los sitios:</b>")
            for i, (domain, count) in enumerate(domains.items(), 1):
                if i > 20:
                    lines.append(f"  ... y {len(domains) - 20} más")
                    break
                lines.append(f"  {i}. {domain} ({count})")

        # Teclado
        lines.append(f"")
        lines.append(f"{'─'*30}")
        lines.append("⌨️ <b>ACTIVIDAD DE TECLADO</b>")
        lines.append(f"  Total pulsaciones: {keyboard_stats.get('total_keypresses', 0)}")

        keypresses_by_app = keyboard_stats.get("keypresses_by_app", {})
        if keypresses_by_app:
            sorted_apps = sorted(keypresses_by_app.items(), key=lambda x: -x[1])[:10]
            lines.append("  Por aplicación:")
            for app, count in sorted_apps:
                lines.append(f"    • {app[:50]}: {count}")

        # Texto capturado por ventana
        if captured_text:
            lines.append(f"")
            lines.append(f"{'\u2500'*30}")
            lines.append("📝 <b>TEXTO ESCRITO POR VENTANA</b>")
            sorted_windows = sorted(captured_text.items(), key=lambda x: -len(x[1]))
            for window, text in sorted_windows[:12]:
                text = text.strip()
                if not text:
                    continue
                preview = text[-300:] if len(text) > 300 else text
                preview = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                short_win = window[:60]
                lines.append(f"")
                lines.append(f"💻 <b>{short_win}</b>")
                lines.append(f"<code>{preview}</code>")

        # Recomendaciones
        lines.append(f"")
        lines.append(f"{'─'*30}")
        lines.append("💡 <b>RECOMENDACIONES</b>")
        recommendations = self._generate_recommendations(
            score, app_classification, url_classification, app_stats
        )
        for rec in recommendations:
            lines.append(f"  • {rec}")

        lines.append(f"")
        lines.append(f"<i>Generado por Cockies Monitor 🍪</i>")

        return "\n".join(lines)

    def generate_idle_notification(self, idle_minutes: float) -> str:
        """Genera notificación de inactividad."""
        return (
            f"😴 <b>Inactividad detectada</b>\n\n"
            f"Llevas <b>{int(idle_minutes)} minutos</b> sin actividad.\n"
            f"¿Estás en un descanso o te distrajiste?"
        )

    def generate_break_reminder(self, active_minutes: float) -> str:
        """Genera recordatorio de tomar un descanso."""
        return (
            f"☕ <b>¡Hora de un descanso!</b>\n\n"
            f"Llevas <b>{int(active_minutes)} minutos</b> de actividad continua.\n"
            f"Recuerda la regla 20-20-20:\n"
            f"Cada 20 min, mira algo a 20 pies (6m) por 20 segundos."
        )

    def generate_distraction_alert(self, app_name: str, time_wasted: float) -> str:
        """Genera alerta de distracción."""
        return (
            f"🚨 <b>Alerta de distracción</b>\n\n"
            f"Llevas <b>{int(time_wasted)} minutos</b> en <b>{app_name}</b>.\n"
            f"¿Es necesario o estás procrastinando?"
        )

    def _score_emoji(self, score: float) -> str:
        if score >= 80:
            return "🟢"
        elif score >= 60:
            return "🟡"
        elif score >= 40:
            return "🟠"
        else:
            return "🔴"

    def _generate_recommendations(self, score: float, app_class: dict,
                                   url_class: dict, app_stats: dict) -> list[str]:
        recommendations = []

        if score < 50:
            recommendations.append(
                "Tu productividad está baja. Intenta usar técnica Pomodoro (25 min trabajo, 5 min descanso)."
            )
        if app_class.get("unproductive_minutes", 0) > 60:
            recommendations.append(
                f"Has pasado {app_class['unproductive_minutes']} min en apps improductivas. "
                f"Considera bloquear distracciones temporalmente."
            )
        if url_class.get("unproductive_count", 0) > 10:
            recommendations.append(
                "Muchas visitas a sitios de distracción. "
                "Intenta agrupar tu navegación recreativa en bloques definidos."
            )
        if app_stats.get("app_switches", 0) > 100:
            recommendations.append(
                f"{app_stats['app_switches']} cambios de ventana indican multitasking excesivo. "
                f"Intenta enfocarte en una tarea a la vez."
            )
        if not recommendations:
            recommendations.append("¡Buen trabajo! Mantén este ritmo. 💪")

        return recommendations
