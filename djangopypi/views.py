""" views.py

Copyright (c) 2009, Ask Solem
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.

Neither the name of Ask Solem nor the names of its contributors may be used
to endorse or promote products derived from this software without specific
prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

"""

from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.http import QueryDict, HttpResponseForbidden
from django.shortcuts import render_to_response
from djangopypi.models import Project
from djangopypi.forms import ProjectRegisterForm
from django.template import RequestContext
from django.utils.datastructures import MultiValueDict
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import authenticate, login
from djangopypi.http import HttpResponseNotImplemented
from djangopypi.http import HttpResponseUnauthorized


def parse_weird_post_data(raw_post_data):
    """ For some reason Django can't parse the HTTP POST data
    sent by ``distutils`` register/upload commands.
    
    This parser should be able to so, and returns a
    :class:`django.utils.datastructures.MultiValueDict`
    as you would expect from a regular ``request.POST`` object.
    """
    # If anyone knows any better way to do this, you're welcome
    # to give me a solid beating. [askh@opera.com]
    sep = raw_post_data.splitlines()[1]
    items = raw_post_data.split(sep)
    post_data = {}
    files = {}
    for part in items:
        if not part.strip():
            continue
        item = part.splitlines()
        if len(item) < 2: continue
        header = item[1].replace("Content-Disposition: form-data; ", "")
        kvpairs = header.split(";")
        headers = {}
        for kvpair in kvpairs:
            if not kvpair: continue
            key, value = kvpair.split("=")
            headers[key] = value.strip('"')
        if not "name" in headers: continue
        content = part[len("\n".join(item[0:2]))+2:len(part)-1]
        if "filename" in headers:
            file = SimpleUploadedFile(headers["filename"], content,
                    content_type="application/gzip")
            files[headers["name"]] = file
        elif headers["name"] in post_data:
            post_data[headers["name"]].append(content)
        else:
            # Distutils sends UNKNOWN for empty fields (e.g platform)
            # [russel.sim@jcu.edu.au]
            if content == 'UNKNOWN':
                post_data[headers["name"]] = [None]
            else:
                post_data[headers["name"]] = [content]

    return MultiValueDict(post_data), files


def login_basic_auth(request):
    authentication = request.META.get("HTTP_AUTHORIZATION")
    if not authentication:
        return
    (authmeth, auth) = authentication.split(' ', 1)
    if authmeth.lower() != "basic":
        return
    auth = auth.strip().decode("base64")
    username, password = auth.split(":", 1)
    return authenticate(username=username, password=password)


def simple(request, template_name="djangopypi/simple.html"):
    if request.method == "POST":
        user = login_basic_auth(request)
        if not user:
            return HttpResponseUnauthorized('PyPI')
        login(request, user)
        if not request.user.is_authenticated():
            return HttpResponseForbidden(
                    "Not logged in, or invalid username/password.")
        post_data, files = parse_weird_post_data(request.raw_post_data)
        action = post_data.get(":action")
        classifiers = post_data.getlist("classifiers")
        register_form = ProjectRegisterForm(post_data.copy())
        if register_form.is_valid():
            try:
                register_form.save(classifiers, request.user,
                        file=files.get("content"))
            except register_form.PermissionDeniedError, e:
                return HttpResonseForbidden(
                        "That project is owned by someone else!")
            except register_form.AlreadyExistsError, e:
                return HttpResponseForbidden(e)
            return HttpResponse("Successfully registered.")
        return HttpResponse("ERRORS: %s" % register_form.errors)

    dists = Project.objects.all().order_by("name")
    context = RequestContext(request, {
        "dists": dists,
        "title": 'Package Index',
    })

    return render_to_response(template_name, context_instance=context)


def show_links(request, dist_name,
        template_name="djangopypi/show_links.html"):
    try:
        project = Project.objects.get(name=dist_name)
        releases = project.releases.all().order_by('-version')
    except Project.DoesNotExist:
        raise Http404

    context = RequestContext(request, {
        "dist_name": dist_name,
        "releases": releases,
        "project": project,
        "title": project.name,
    })

    return render_to_response(template_name, context_instance=context)


def show_version(request, dist_name, version,
        template_name="djangopypi/show_version.html"):
    try:
        release = Project.objects.get(name=dist_name).releases \
                                        .get(version=version)
    except Project.DoesNotExist:
        raise Http404()

    context = RequestContext(request, {
        "dist_name": dist_name,
        "version": version,
        "release": release,
        "title": dist_name,
    })

    return render_to_response(template_name, context_instance=context)
