from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class TosAcceptanceHandler(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated \
                and 'terms_acceptance_form' not in request.get_full_path() \
                and 'logout' not in request.get_full_path():

            user = request.user
            if not user.profile.accepted_terms:
                return redirect(reverse("terms-acceptance-form"))

        response = self.get_response(request)

        return response
