from users.models import Notification

def global_notifications(request):
    """Injecte unread_notifications_count dans le contexte de tous les templates"""
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
