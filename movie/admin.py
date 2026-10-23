from django.contrib import admin

from movie import models

admin.site.register(models.Movie)
admin.site.register(models.Genre)
admin.site.register(models.Person)
admin.site.register(models.MovieCast)
admin.site.register(models.Watchlist)
admin.site.register(models.Rating)
admin.site.register(models.Comment)
admin.site.register(models.CommentLike)
