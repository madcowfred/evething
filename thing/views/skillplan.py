# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import gzip
import json
import datetime
import thread
import StringIO

from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import F
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from core.util import json_response
from thing.forms import UploadSkillPlanForm
from thing.models import *
from thing.stuff import *
from thing.utils.eftparser import EFTParser


# ---------------------------------------------------------------------------
# Delete all entries from a skillplan 
@login_required
def skillplan_ajax_clean(request, skillplan_id):
    if request.is_ajax():
        if skillplan_id.isdigit():
            try:
                skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
            
            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     
             
            # Delete all of the random things for this skillplan
            entries = SPEntry.objects.filter(skill_plan=skillplan)
            SPRemap.objects.filter(pk__in=[e.sp_remap_id for e in entries if e.sp_remap_id]).delete()
            SPSkill.objects.filter(pk__in=[e.sp_skill_id for e in entries if e.sp_skill_id]).delete()
            entries.delete()
                
            return HttpResponse(json.dumps({'status':'ok'}), status=200)
            
        else:
            return HttpResponse(content='Cannot delete the entry : no skillplan or entry given', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)

# ---------------------------------------------------------------------------
# Add a remap to the skillplan
@login_required
def skillplan_ajax_add_remap(request, skillplan_id):
    """
    Add a remap to the skillplan
        
    This function will return a json with status "ok" or a http error code.
    
    POST:   skillplan_id : id of the plan
    """
    tt = TimerThing('skill_add_skill')

    tt.add_time('init')
    
    if request.is_ajax():
        
        if skillplan_id.isdigit():
            try:
                skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)

            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     

            last_position = skillplan.entries.count();
            tt.add_time('SkillPlan last pos')
                        
            skill_remap = SPRemap.objects.create(
                int_stat=20,
                mem_stat=20,
                per_stat=20,
                wil_stat=20,
                cha_stat=19,
            )

            SPEntry.objects.create(
                skill_plan=skillplan,
                position=last_position,
                sp_remap=skill_remap,
            )
            
            tt.add_time('Remap entry creation')
            if settings.DEBUG:
                tt.finished()    
                
            return HttpResponse(json.dumps({'status':'ok'}), status=200)
        
        else:
            return HttpResponse(content='Cannot add the remap : no skillplan provided', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)

# ---------------------------------------------------------------------------
# Add a given skill & prerequisites
@login_required
def skillplan_ajax_add_skill(request, skillplan_id):
    """
    Add a skill and all of it's prerequisite (not already in the plan)
    into the skill plan
    
    This function will return a json with status "ok" or a http error code.
    
    POST:   skillplan_id : id of the plan
            skill_id : skill to add 
            skill_level : the level of the skill to add
    """
    tt = TimerThing('skill_add_skill')

    tt.add_time('init')
    
    if request.is_ajax():
        skill_id        = request.POST.get('skill_id', '')
        skill_level     = request.POST.get('skill_level', '')
        
        if not skill_level.isdigit() or int(skill_level) < 1 or int(skill_level) > 5:
            skill_level = 1
        skill_level = int(skill_level)
        
        if skill_id.isdigit() and skillplan_id.isdigit():
            try:
                skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
                skill = Skill.objects.get(item__id=skill_id)
                
            except Skill.DoesNotExist:
                return HttpResponse(content='That skill does not exist', status=500) 
                
            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     

            skill_list = []
            seen = {}
            last_position = 0
            
            tt.add_time('Get objects')
            
            # get the list of all skills already in the plan
            for entry in skillplan.entries.select_related('sp_skill__skill__item'):         
                if entry.sp_skill is not None:
                    seen[entry.sp_skill.skill.item_id] = entry.sp_skill.level
                last_position = entry.position + 1
            
            tt.add_time('Get skillplan entries')
            
            # if the skill is not already in the plan at the same level, we'll try to add it.
            if (skill.item_id in seen and skill_level > seen[skill.item_id]) or skill.item_id not in seen:
            
                # fetch all prerequisites
                skill_list = skill.item.get_flat_prerequisites()
                
                # finally add the current skill 
                skill_list.append((skill.item_id, skill_level)) 
                
                tt.add_time('Get skills prerequisites')
                
            
            # if we have any new skill to add, just create the new entries :)
            entries = []
            
            for skill_id, level in skill_list:
                for l in range(seen.get(skill_id, 0) + 1, level + 1):
                    try:
                        sps = SPSkill.objects.create(
                            skill_id = skill_id,
                            level = l,
                            priority=3,
                        )
                    except:
                        continue
                        
                    seen[skill_id] = l
                    
                    entries.append(SPEntry(
                        skill_plan=skillplan,
                        position=last_position,
                        sp_skill=sps,
                    ))

                    last_position += 1
                
            SPEntry.objects.bulk_create(entries)
            
            tt.add_time('Skill Entries creation')
            if settings.DEBUG:
                tt.finished()    
                
            return HttpResponse(json.dumps({'status':'ok'}), status=200)
        
        else:
            return HttpResponse(content='Cannot add the skill : no skill or no skillplan provided', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)

# ---------------------------------------------------------------------------
# Delete an entry and all of its dependencies 
@login_required
def skillplan_ajax_delete_entry(request, skillplan_id):
    """
    Remove an entry from the skillplan, also remove all the skill dependencies if required
        
    This function will return a json with status "ok" or a http error code.
    
    POST:   skillplan_id : id of the plan
    """
    tt = TimerThing('skill_delete_entry')

    tt.add_time('init')
    
    if request.is_ajax():
        entry_id         = request.POST.get('entry_id', '')

        if skillplan_id.isdigit() and entry_id.isdigit():
            try:
                skillplan   = SkillPlan.objects.get(user=request.user, id=skillplan_id)
                del_entry   = SPEntry.objects.select_related('sp_remap', 'sp_skill__skill__item').get(id=entry_id)

            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     


            except SPEntry.DoesNotExist:
                return HttpResponse(content='That entry does not exist', status=500)     

            tt.add_time('Get objects')
            
            nb_entry_deleted = 1

            entries = (
                skillplan.entries
                .select_related('sp_skill__skill__item')
                .filter(position__gt = del_entry.position)
            )
            
            for entry in entries:
                if del_entry.sp_skill is not None and entry.sp_skill is not None:
                    if  (del_entry.sp_skill.skill.is_unlocked_by_skill(entry.sp_skill.skill.item, del_entry.sp_skill.level) or
                        (del_entry.sp_skill.skill.item_id == entry.sp_skill.skill.item_id and 
                            del_entry.sp_skill.level < entry.sp_skill.level)):
                        
                        entry.sp_skill.delete()
                        entry.delete()
                        nb_entry_deleted += 1
                        continue
                    
                entry.position -= nb_entry_deleted           
                entry.save(update_fields=['position'])
            
            if del_entry.sp_skill is not None:
                del_entry.sp_skill.delete()
            else: 
                del_entry.sp_remap.delete()
            del_entry.delete()
            
            tt.add_time('Delete')
            
            if settings.DEBUG:
                tt.finished()   
                
            return HttpResponse(json.dumps({'status':'ok'}), status=200)
        
        else:
            return HttpResponse(content='Cannot delete the entry : no skillplan or entry given', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)

# ---------------------------------------------------------------------------
# Import the skill related to an EFT Textblock into the skillplan 
@login_required
def skillplan_ajax_import_eft(request, skillplan_id):
    """
        Add skills into the skillplan using an EFT Textblock.
        
        POST : eft_textblock
        RETURN : json with status, skills injected, skills not injected
    """
    tt = TimerThing('skillplan_import_eft_textblock')

    tt.add_time('init')
    
    if request.is_ajax():
    
        eft_text_block = request.POST.get('eft_textblock', '').strip()
        
        if len(eft_text_block) == 0:
            return HttpResponse(content='EFT Text block cannot be empty', status=500)
        
        if skillplan_id.isdigit():
            try:
                skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)

            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     

            eft_parsed = EFTParser.parse(eft_text_block)

            skill_list    = []
            seen          = {}
            response      = {'fail':[]}
            last_position = 0
                        
            tt.add_time('Get objects')
            
            # get the list of all skills already in the plan
            entries = skillplan.entries.select_related('sp_skill__skill__item')
            
            for entry in entries:         
                if entry.sp_skill is not None:
                    seen[entry.sp_skill.skill.item_id] = entry.sp_skill.level
                last_position = entry.position + 1
            
            tt.add_time('Get skillplan entries')
            
            if eft_parsed['ship_type']:
                try:
                    ship = Item.objects.get(name=eft_parsed['ship_type'])
                    skill_list = ship.get_flat_prerequisites()
                    
                except Item.DoesNotExist:
                    response['fail'].append(eft_parsed['ship_type'])
            
            # get all modules skill prereqs
            for items in eft_parsed['modules']:
                item_name   = items['name']
                charge_name = items['charge']

                try:
                    item        = Item.objects.get(name = item_name)
                    skill_list  = skill_list+item.get_flat_prerequisites()
                    
                except Item.DoesNotExist:
                    response['fail'].append(item_name)
                
                if charge_name:
                    try:
                        charge      = Item.objects.get(name = charge_name)
                        skill_list  = skill_list+charge.get_flat_prerequisites()
                        
                    except Item.DoesNotExist:
                        response['fail'].append(charge_name)
            
            # get all charges and drones skill prereqs
            for items in eft_parsed['cargodrones']:
                item_name   = items['name']
                try:
                    item        = Item.objects.get(name = item_name)
                    skill_list  = skill_list+item.get_flat_prerequisites()
                    
                except Item.DoesNotExist:
                    response['fail'].append(item_name)

            tt.add_time('Get items prereqs')
            
            # if we have any new skill to add, just create the new entries :)
            added_entries = []
            
            for skill_id, level in skill_list:
                for l in range(seen.get(skill_id, 0) + 1, level + 1):
                    try:
                        sps = SPSkill.objects.create(
                            skill_id = skill_id,
                            level = l,
                            priority=3,
                        )
                    except:
                        continue
                        
                    seen[skill_id]    = l
                    
                    added_entries.append(SPEntry(
                        skill_plan=skillplan,
                        position=last_position,
                        sp_skill=sps,
                    ))

                    last_position += 1
                
            SPEntry.objects.bulk_create(added_entries)
            
            tt.add_time('Skill Entries creation')
            if settings.DEBUG:
                tt.finished()    
            
            response['status']  = 'ok'
            return HttpResponse(json.dumps(response), status=200)


# ---------------------------------------------------------------------------
# Optimize remap for each remap point for a given skillplan
@login_required
def skillplan_ajax_optimize_remaps(request, skillplan_id):
    tt = TimerThing('skillplan_opti_remaps')

    tt.add_time('init')
    
    if request.is_ajax():
        
        if skillplan_id.isdigit():
            try:
                skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)

            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     
            
            # we want all remaps from the end to beginning of the plan
            remaps = skillplan.entries.select_related('sp_remap').filter(sp_remap__isnull=False).order_by('-position')
            
            # prefetch all entries, not to have a query for each entries per remaps
            entries = skillplan.entries.select_related('sp_remap', 'sp_skill__skill__item')
            end_position = entries.count();
            
            tt.add_time('get entries') 
            remap_list=[]
            
            
            for remap in remaps:
                start_position = remap.position
                current_remap_entries = entries.filter(position__gt=start_position, position__lt=end_position)
                remapped_attribute = _optimize_attribute(current_remap_entries, datetime.timedelta.max.days * 24 * 60 * 60)
                
                remap.sp_remap.int_stat = remapped_attribute['int_attribute']
                remap.sp_remap.mem_stat = remapped_attribute['mem_attribute']
                remap.sp_remap.per_stat = remapped_attribute['per_attribute']
                remap.sp_remap.wil_stat = remapped_attribute['wil_attribute']
                remap.sp_remap.cha_stat = remapped_attribute['cha_attribute']
                
                remap.sp_remap.save()
                
                remap_list.append(remapped_attribute)
                
                end_position = remap.position
            
            
            tt.add_time('remap')
            if settings.DEBUG:
                tt.finished()    
            
            response = {'status':'ok'}
            response['remaps'] = remap_list.reverse()
            return HttpResponse(json.dumps(response), status=200)
        
        else:
            return HttpResponse(content='Cannot optimize remaps for skillplan : no skillplan provided', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)

# ---------------------------------------------------------------------------
# Render the table entries of the skillplan
@login_required
def skillplan_ajax_render_entries(request, skillplan_id, character_id, implants, show_trained):
    skillplan = get_object_or_404(SkillPlan, user=request.user, pk=skillplan_id)
    
    try:
        character = Character.objects.select_related('config','details').get(apikeys__user=request.user, id=character_id)
    except Character.DoesNotExist:
        character = False
    
    if implants.isdigit() and 0 <= int(implants) <= 5:
        implants = int(implants)
    else:
        implants = 0 
    
    show_trained=bool(int(show_trained))
    
    return _skillplan_list_json(request, skillplan, character, implants, show_trained)

# ---------------------------------------------------------------------------
# Move an entry in another position
@login_required
def skillplan_ajax_reorder_entry(request, skillplan_id):
    """
    Add a remap to the skillplan
        
    This function will return a json with status "ok" or a http error code.
    
    GET:    skillplan_id
    POST:   moved_entry_id 
    POST:   new_position
    """
    tt = TimerThing('skillplan_reorder_entry')

    tt.add_time('init')
    
    if request.is_ajax():
        moved_entry_id   = request.POST.get('entry_id', '')
        new_position     = request.POST.get('new_position', '')

        if skillplan_id.isdigit() and moved_entry_id.isdigit() and new_position.isdigit():
            new_position = int(new_position)
            try:
                skillplan   = SkillPlan.objects.get(user=request.user, id=skillplan_id)
                moved_entry = SPEntry.objects.select_related('sp_remap', 'sp_skill__skill__item').get(id=moved_entry_id)

            except SkillPlan.DoesNotExist:
                return HttpResponse(content='That skillplan does not exist', status=500)     


            except SPEntry.DoesNotExist:
                return HttpResponse(content='That entry does not exist', status=500)     

            last_position = skillplan.entries.count();
            
            if new_position < 0:
                new_position = 0
            elif new_position >= last_position:
                new_position = last_position-1
                
            tt.add_time('Fix new position')

            skill_relatives = []
                
            # get entries and count prereqs skills/unlocked item 
            # - Moving upward
            if new_position < moved_entry.position:
                entries = skillplan.entries.select_related('sp_skill__skill__item') \
                                   .filter(position__lt = moved_entry.position, position__gte = new_position) \
                                   .only('position','sp_skill')
                delta_position = 1

                # check the number of prerequisite if we move a skill
                if moved_entry.sp_remap is None:
                    moved_skill = moved_entry.sp_skill.skill
                    for entry in entries:
                        if entry.sp_remap is not None:
                            continue
                        
                        if moved_skill.item.is_prerequisite(entry.sp_skill.skill, entry.sp_skill.level) or \
                          (moved_skill.item_id == entry.sp_skill.skill.item_id and moved_entry.sp_skill.level > entry.sp_skill.level):
                            skill_relatives.append(entry.id)   

            # - Moving downward                
            elif new_position > moved_entry.position:
                entries = skillplan.entries.select_related('sp_skill__skill__item') \
                                   .filter(position__gt = moved_entry.position, position__lte = new_position) \
                                   .order_by('-position') \
                                   .only('position','sp_skill')
                delta_position = -1
                
                # check the number of unlocked_skills if we move a skill
                if moved_entry.sp_remap is None:
                    moved_skill = moved_entry.sp_skill.skill
                    for entry in entries:
                        if entry.sp_remap is not None:                        
                            continue
                            
                        if moved_skill.is_unlocked_by_skill(entry.sp_skill.skill.item, moved_entry.sp_skill.level) or \
                          (moved_skill.item_id == entry.sp_skill.skill.item_id and moved_entry.sp_skill.level < entry.sp_skill.level):
                            skill_relatives.append(entry.id)

            # - Same position
            else:   
                return HttpResponse(json.dumps({'status':'nothing_changed'}), status=200)
            
            tt.add_time('Entries')
           
            # loop on entries
            # add to entry position : 
            # - if not prerequisite or unlocked_skills : entry.position += delta_position + (delta_position * number of prerequisite not already moved)
            # - if prerequisite or unlocked_skills : entry.position = new_position, new_position -= delta_position
            # loop.
            # moved_entry.position = new_position

            if moved_entry.sp_remap is None:
                for entry in entries:
                
                    if entry.id in skill_relatives:
                        skill_relatives.remove(entry.id)
                        entry.position = new_position
                        new_position += delta_position
                        entry.save(update_fields=['position'])
                        continue
                    
                    entry.position += delta_position + (delta_position * len(skill_relatives))                   
                    entry.save(update_fields=['position'])
                        
            else:
                entries.update(position=F('position') + delta_position)
            
            moved_entry.position = new_position
            moved_entry.save(update_fields=['position'])
            
            tt.add_time('Reorder')
            
            if settings.DEBUG:
                tt.finished()   
                
            return HttpResponse(json.dumps({'status':'ok'}), status=200)
        
        else:
            return HttpResponse(content='Cannot add the remap : no skillplan provided, entry or position given', status=500)       
    else:
        return HttpResponse(content='Cannot call this page directly', status=403)


# ---------------------------------------------------------------------------
# List all skillplans
@login_required
def skillplan(request):    
    if 'message' in request.session:
        message = request.session.pop('message')
        message_type = request.session.pop('message_type')
    else:
        message = None
        message_type = None

    return render_page(
        'thing/skillplan.html',
        {
            'message': message,
            'message_type': message_type,
            'skillplans': SkillPlan.objects.filter(user=request.user).order_by('id'),
            'visibilities': SkillPlan.VISIBILITY_CHOICES,
        },
        request,
    )

# ---------------------------------------------------------------------------
# Create a skillplan
@login_required
def skillplan_edit(request, skillplan_id):

    if skillplan_id.isdigit():
        skillplan = get_object_or_404(SkillPlan, user=request.user, pk=skillplan_id)
        characters = Character.objects.filter(apikeys__user=request.user).select_related('config','details').distinct()
            
        # Init the global skill list
        skill_list           = OrderedDict()
        current_market_group = None

        skills = Skill.objects.filter(item__market_group__isnull=False)
        skills = skills.select_related('item__market_group')
        skills = skills.order_by('item__market_group__name', 'item__name')
        
        for skill in skills:
            market_group = skill.item.market_group
            if market_group != current_market_group:
                current_market_group = market_group
                skill_list[current_market_group] = []
            
            skill_list[current_market_group].append(skill)
        
        return render_page(
            'thing/skillplan_edit.html',
            {   
                'skillplan'         : skillplan,
                'skill_list'        : skill_list,
                'characters'        : characters,
                'marketgroup_list'  : MarketGroup.objects.filter(parent=None).select_related('items').all(),
            },
            request,
        )

    else:
        redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------
# Import a skillplan
@login_required
def skillplan_import_emp(request):
    if request.method == 'POST':
        form = UploadSkillPlanForm(request.POST, request.FILES)
        if form.is_valid():
            _handle_skillplan_upload(request)
            return redirect('thing.views.skillplan')
        else:
            request.session['message_type'] = 'error'
            request.session['message'] = 'Form validation failed!'
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a POST request!"

    return redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------
# Create a skillplan
@login_required
def skillplan_create(request):
    if request.method == 'POST':
        skillplan = SkillPlan.objects.create(
            user=request.user,
            name=request.POST['name'],
            visibility=request.POST['visibility'],
        )
        
        skillplan.save()
        request.session['message_type'] = 'success'
        request.session['message'] = "Skill plan %s uploaded successfully." % request.POST['name']
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a POST request!"
    
    return redirect('thing.views.skillplan')
    

# ---------------------------------------------------------------------------
# Export Skillplan
@login_required
def skillplan_export(request, skillplan_id):
    if skillplan_id.isdigit():
        skillplan = get_object_or_404(SkillPlan, user=request.user, pk=skillplan_id)     
        # register namespaces 
        xsi = "http://www.w3.org/2001/XMLSchema-instance" 
        xsd = "http://www.w3.org/2001/XMLSchema"
        
        # since we want to use "tostring" and not "write", we need to manually add
        # namespace declaration into "plan" node...
        # <plan xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" name="test">
        plan_attributes = {
            'name':skillplan.name,
            'xmlns:xsi':xsi,
            'xmlns:xsd':xsd,
            'revision':'4116',
        }
        root = ET.Element('plan', plan_attributes)
        
        # <sorting criteria="None" order="None" groupByPriority="false" />
        sorting_attributes = {
            'criteria':'None',
            'order':'None',
            'groupByPriority':'false',
        }
        root.append(ET.Element('sorting', sorting_attributes))
        
        
        # now loop on entries, and fill that xml
        remap_element = None
        for entry in skillplan.entries.select_related('sp_remap', 'sp_skill__skill__item__item_group'):
            
            if entry.sp_remap is not None:
                #   <remapping status="UpToDate" per="27" int="17" mem="17" wil="21" cha="17" 
                #               description="" />
                description = '&#xD;&#xA;Intelligence (-3) = 17 = (17 + 0 + 0) \
                               &#xD;&#xA;Perception (+7) = 27 = (17 + 10 + 0) \
                               &#xD;&#xA;Charisma (-2) = 17 = (17 + 0 + 0) \
                               &#xD;&#xA;Willpower (+1) = 21 = (17 + 4 + 0) \
                               &#xD;&#xA;Memory (-3) = 17 = (17 + 0 + 0)'
                               
                remap_attributes = {
                    'int':str(entry.sp_remap.int_stat),
                    'mem':str(entry.sp_remap.mem_stat),
                    'per':str(entry.sp_remap.per_stat),
                    'wil':str(entry.sp_remap.wil_stat),
                    'cha':str(entry.sp_remap.cha_stat),
                    'status':'UpToDate',
                    'description':'this is a remap...'
                }
                remap_element = ET.Element('remapping', remap_attributes)
                continue
            
            #<entry skillID="ID" skill="skill_name" level="" priority="3" type="Planned">
            #   <notes>skill_name</notes>
            
            entry_attributes = {
                'skillID':str(entry.sp_skill.skill.item_id),
                'skill':entry.sp_skill.skill.item.name,
                'level':str(entry.sp_skill.level),
                'priority':str(entry.sp_skill.priority),
                'type':'Planned',
            }
            entry_element = ET.Element('entry', entry_attributes)
            notes = ET.Element('notes')
            notes.text = entry.sp_skill.skill.item.name
            entry_element.append(notes)
            
            if remap_element is not None:
                entry_element.append(remap_element)
                remap_element = None
            
            root.append(entry_element)
        
        xml_string = StringIO()
        f = gzip.GzipFile(fileobj=xml_string, mode='w')
        f.write(ET.tostring(root))
        f.close()

        
        response = HttpResponse(xml_string.getvalue(), content_type='application/x-gzip')
        response['Content-Disposition'] = 'attachment; filename=%s.emp' % skillplan.name
        return response
        
    else:
        redirect('thing.views.skillplan')
        

# ---------------------------------------------------------------------------
# Delete a skillplan
@login_required
def skillplan_delete(request):
    skillplan_id = request.POST.get('skillplan_id', '')
    if skillplan_id.isdigit():
        try:
            skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
        
        except SkillPlan.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not own that skill plan!'
        
        else:
            request.session['message_type'] = 'success'
            request.session['message'] = 'Skill plan "%s" deleted successfully!' % (skillplan.name)
            
            # Delete all of the random things for this skillplan
            entries = SPEntry.objects.filter(skill_plan=skillplan)
            SPRemap.objects.filter(pk__in=[e.sp_remap_id for e in entries if e.sp_remap_id]).delete()
            SPSkill.objects.filter(pk__in=[e.sp_skill_id for e in entries if e.sp_skill_id]).delete()
            entries.delete()
            skillplan.delete()

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------
# Edit a skillplan
@login_required
def skillplan_edit_info(request):
    skillplan_id = request.POST.get('skillplan_id', '')
    if skillplan_id.isdigit():
        try:
            skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)
        
        except SkillPlan.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not own that skill plan!'
        
        else:
            skillplan.name = request.POST['name']
            skillplan.visibility = request.POST['visibility']
            skillplan.save()

            request.session['message_type'] = 'success'
            request.session['message'] = 'Skill plan "%s" edited successfully!' % (skillplan.name)

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('thing.views.skillplan')

# ---------------------------------------------------------------------------
# Return the entries of a given skillplan
def _skillplan_list_json(request, skillplan, character, implants, show_trained):
    tt = TimerThing('skillplan_list_entries_json')

    utcnow = datetime.datetime.utcnow()

    tt.add_time('init')

    # Init some stuff to have no errors
    learned = {}
    training_skill = None
    # Try retrieving learned data from cache
    if character:
        cache_key = 'character_skillplan:learned:%s' % (character.id)
        learned = cache.get(cache_key)
        # Not cached, fetch from database and cache
        if learned is None:
            learned = {}
            for cs in CharacterSkill.objects.filter(character=character).select_related('skill__item'):
                learned[cs.skill.item_id] = cs
            cache.set(cache_key, learned, 300)
    
        tt.add_time('char skills')
    
        # Possibly get training information
        training_skill = None
        if character.config.show_skill_queue is True:
            sqs = list(SkillQueue.objects.select_related('skill__item').filter(character=character, end_time__gte=utcnow))
            if sqs:
                training_skill = sqs[0]
    
        tt.add_time('training')
        
    # Initialise stat stuff
    if character and character.details:
        remap_stats = dict(
            int_attribute=character.details.int_attribute,
            mem_attribute=character.details.mem_attribute,
            per_attribute=character.details.per_attribute,
            wil_attribute=character.details.wil_attribute,
            cha_attribute=character.details.cha_attribute,
        )
        
    else:
        # default stats on a new char
        # no char will ever have 0 to any attribute
        remap_stats = dict(
            int_attribute=20,
            mem_attribute=20,
            per_attribute=20,
            wil_attribute=20,
            cha_attribute=19,
        )

    implant_stats = {}
    for stat in ('int', 'mem', 'per', 'wil', 'cha'):
        k = '%s_bonus' % (stat)
        if implants == 0 and character:
            implant_stats[k] = getattr(character.details, k, 0)
        else:
            implant_stats[k] = implants

    # Iterate over all entries in this skill plan
    skillplan_json = {
        'remaining_duration':0.0,
        'total_duration':0.0,
        'entries':[],
    }
    
    sp_remap = None

    for entry in skillplan.entries.select_related('sp_remap', 'sp_skill__skill__item__item_group'):
        sp_entry = {
            'id': entry.id,
            'position': entry.position,
            'remap':None,
            'skill':None,
        }
        
        # It's a remap entry
        if entry.sp_remap is not None:
        
            # If the remap have every attributes set to 0, we do not add it.
            # (happen when remap are not set on evemon before exporting .emp
            if entry.sp_remap.int_stat == 0 and entry.sp_remap.mem_stat == 0 and \
               entry.sp_remap.per_stat == 0 and entry.sp_remap.wil_stat == 0 and entry.sp_remap.cha_stat == 0:
               continue
                
            
            # Delete the previous remap if it's two in a row, that makes no sense
            if skillplan_json['entries'] and skillplan_json['entries'][-1]['remap'] is not None:
                skillplan_json['entries'].pop()
            
            remap_stats['int_attribute'] = entry.sp_remap.int_stat
            remap_stats['mem_attribute'] = entry.sp_remap.mem_stat
            remap_stats['per_attribute'] = entry.sp_remap.per_stat
            remap_stats['wil_attribute'] = entry.sp_remap.wil_stat
            remap_stats['cha_attribute'] = entry.sp_remap.cha_stat
            
            sp_remap = {
                'int':remap_stats['int_attribute'],
                'mem':remap_stats['mem_attribute'],
                'per':remap_stats['per_attribute'],
                'wil':remap_stats['wil_attribute'],
                'cha':remap_stats['cha_attribute'],
                'duration':0,
                'total_duration':0,
            }
            
            sp_entry['remap'] = sp_remap

        # It's a skill entry
        if entry.sp_skill is not None:
            skill = entry.sp_skill.skill
            
            sp_skill = {
                'id':skill.item_id,
                'name':skill.item.name,
                'group':skill.item.item_group.name,
                'level':entry.sp_skill.level,
                'primary':skill.get_primary_attribute_display(),
                'secondary':skill.get_secondary_attribute_display(),
                'injected':False,
                'training':False,
                'percent_trained':0,
                'spph':0,
                'remaining_time':0,
            }
            
            # If this skill is already learned
            char_skill = learned.get(skill.item_id, None)
            if char_skill is not None:
                # Mark it as injected if level 0
                if char_skill.level == 0:
                    sp_skill['injected'] = True
                    
                # It might already be trained
                elif char_skill.level >= entry.sp_skill.level:
                
                    # If we don't care about trained skills, skip this skill entirely
                    if not show_trained:
                        continue

                    sp_skill['percent_trained'] = 100
                    sp_skill['remaining_time'] = 0
                
                # Partially trained ?
                # check if current skill SP > level SP AND planned skill lvl - 1 = learned skill level
                elif char_skill.points > char_skill.skill.get_sp_at_level(char_skill.level) and entry.sp_skill.level-1 == char_skill.level:
                    required_sp = char_skill.skill.get_sp_at_level(char_skill.level + 1) - char_skill.skill.get_sp_at_level(char_skill.level)
                    sp_skill['sp_done'] = char_skill.points-char_skill.skill.get_sp_at_level(char_skill.level)
                    sp_skill['percent_trained'] = round(sp_skill['sp_done'] / float(required_sp) * 100, 1)

            # Calculate SP/hr
            if remap_stats:
                sp_per_min = skill.get_sppm_stats(remap_stats, implant_stats)
            else:
                sp_per_min = skill.get_sp_per_minute(character)
            
            # cannot have 0 for spph as 0/0/0/0/0 is impossible here 
            sp_skill['spph'] = sp_per_min * 60

            # Calculate time remaining
            if training_skill is not None and training_skill.skill_id == entry.sp_skill.skill_id and training_skill.to_level == entry.sp_skill.level:
                sp_skill['remaining_time'] = (training_skill.end_time - utcnow).total_seconds()
                sp_skill['total_time'] = (training_skill.end_time - training_skill.start_time).total_seconds()
                sp_skill['training'] = True
                sp_skill['percent_trained'] = training_skill.get_complete_percentage()
                
                
            elif sp_skill['percent_trained'] < 100 and sp_skill['percent_trained'] > 0:
                remaining_sp = skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1) - sp_skill['sp_done']
                sp_skill['remaining_time'] = (remaining_sp) / sp_per_min * 60
                sp_skill['total_time'] = (remaining_sp + sp_skill['sp_done']) / sp_per_min * 60
                print(remaining_sp , sp_skill['sp_done'])
            else:
                required_sp = skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1)
                sp_skill['remaining_time'] = required_sp / sp_per_min * 60

            # Add time remaining to total
            if sp_skill['percent_trained'] != 100:
                skillplan_json['remaining_duration'] += sp_skill['remaining_time']
                
                if sp_remap is not None:
                    sp_remap['duration'] += sp_skill['remaining_time']
                
            # Total duration, includes already trained skill (to get the whole skillplan duration)
            if sp_skill['percent_trained'] < 100 and sp_skill['percent_trained'] > 0:
                skillplan_json['total_duration'] += sp_skill['total_time']
                if sp_remap is not None:
                    sp_remap['total_duration'] += sp_skill['total_time']
            else:
                skillplan_json['total_duration'] += sp_skill['remaining_time']
                if sp_remap is not None:
                    sp_remap['total_duration'] += sp_skill['remaining_time']
                        
            sp_entry['skill'] = sp_skill
            
        skillplan_json['entries'].append(sp_entry)     
           
    tt.add_time('skillplan loop')
    if settings.DEBUG:
        tt.finished()

    return json_response(skillplan_json)
    

# ---------------------------------------------------------------------------
# Handle the upload of a .EMP skillplan 
def _handle_skillplan_upload(request):
    name = request.POST['name'].strip()
    uf = request.FILES['file']
    visibility = request.POST['visibility']

    # Check that this name is unique for the user
    if SkillPlan.objects.filter(user=request.user, name=name).count() > 0:
        request.session['message_type'] = 'error'
        request.session['message'] = "You already have a skill plan with that name!"
        return

    # Check file size, 10KB should be more than large enough
    if uf.size > 10240:
        request.session['message_type'] = 'error'
        request.session['message'] = "That file is too large!"
        return

    data = StringIO(uf.read())

    # Try opening it as a gzip file
    gf = gzip.GzipFile(fileobj=data)
    try:
        data = gf.read()
    except IOError:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a .EMP file!"
        return

    # Make sure it's valid XML
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a .EMP file!"
        return

    # FINALLY
    skillplan = SkillPlan.objects.create(
        user=request.user,
        name=name,
        visibility=visibility,
    )
    
    _parse_emp_plan(skillplan, root)

    request.session['message_type'] = 'success'
    request.session['message'] = "Skill plan %s uploaded successfully." % name

# ---------------------------------------------------------------------------
# Parse an emp skillplan and save it into the database
def _parse_emp_plan(skillplan, root):
    entries = []
    position = 0
    seen = {}
    for entry in root.findall('entry'):
        # Create the various objects for the remapping if it exists
        remapping = entry.find('remapping')
        if remapping is not None:
            # <remapping status="UpToDate" per="17" int="27" mem="21" wil="17" cha="17" description="" />
            spr = SPRemap.objects.create(
                int_stat=remapping.attrib['int'],
                mem_stat=remapping.attrib['mem'],
                per_stat=remapping.attrib['per'],
                wil_stat=remapping.attrib['wil'],
                cha_stat=remapping.attrib['cha'],
            )

            entries.append(SPEntry(
                skill_plan=skillplan,
                position=position,
                sp_remap=spr,
            ))

            position += 1
        
        # Grab some data we'll need
        skillID = int(entry.attrib['skillID'])
        level = int(entry.attrib['level'])
        priority = int(entry.attrib['priority'])
        
        try:
            skill = Skill.objects.get(item__id=skillID)
                
        except Skill.DoesNotExist:
            continue
        
        # fetch prerequisites
        skill_list = skill.item.get_flat_prerequisites()
        
        # and add the current skill 
        skill_list.append((skillID, level)) 
 
        for skill_id, skill_level in skill_list:
            for l in range(seen.get(skill_id, 0) + 1, skill_level + 1):
                try:
                    sps = SPSkill.objects.create(
                        skill_id = skill_id,
                        level = l,
                        priority=priority,
                    )
                except:
                    continue
                    
                seen[skill_id] = l
                
                entries.append(SPEntry(
                    skill_plan=skillplan,
                    position=position,
                    sp_skill=sps,
                ))

                position += 1

    SPEntry.objects.bulk_create(entries)
    

# ---------------------------------------------------------------------------
# Return the best remap for a given entries list
def _optimize_attribute(entries, max_duration):
    max_remap_points_per_attr = 10
    max_spare_points_on_remap = 14
    base_attribute_points = 17
    max_implant_points = 5
    
    best_skill_count = 0
    best_duration = max_duration

    implant_stats = {'int_bonus' : 0, 'mem_bonus' : 0, 'per_bonus' : 0, 'wil_bonus' : 0, 'cha_bonus' : 0}
    
    # max combination number : 11^4 = 14,641
    # PER
    for per in range (0,max_remap_points_per_attr+1):
        
        # WIL
        max_wil = max_spare_points_on_remap - per
        max_wil_range = min(max_wil, max_remap_points_per_attr)
        for wil in range (0, max_wil_range + 1):
        
            # INT
            max_int = max_wil - wil
            max_int_range = min(max_int, max_remap_points_per_attr)
            for int in range (0,max_int_range + 1):
                
                # MEM
                max_mem = max_int - int
                max_mem_range = min(max_mem, max_remap_points_per_attr)
                for mem in range (0,max_mem_range + 1):
                
                    # CHA
                    cha = max_mem - mem
                    
                    if cha > max_remap_points_per_attr: 
                        continue
            
                    remap_stats = dict(
                        int_attribute=base_attribute_points + int,
                        mem_attribute=base_attribute_points + mem,
                        per_attribute=base_attribute_points + per,
                        wil_attribute=base_attribute_points + wil,
                        cha_attribute=base_attribute_points + cha,
                    )
                    
                    current_remap_duration = 0
                    current_skill_count = 0

                    
                    
                    for entry in entries:   
                        if entry.sp_remap is not None:
                            continue
                            
                        skill = entry.sp_skill.skill
                        
                        sp_per_min = skill.get_sppm_stats(remap_stats, implant_stats)
                        
                        current_skill_count += 1
                        current_remap_duration += (skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1)) / sp_per_min * 60
                        
                        # did we just go over max_duration ?
                        if current_remap_duration > max_duration:
                            break
                            
                        # did we do less skill in more time than best duration ?
                        if current_skill_count <= best_skill_count and current_remap_duration > best_duration:
                            break
                    
                    # did we manage to train more skill before the max duration, or did we train the same number in lesser time ?
                    if current_skill_count <= best_skill_count and (current_skill_count != best_skill_count or current_remap_duration >= best_duration):
                        continue
                    
                    if best_duration > current_remap_duration:
                        
                        best_skill_count = current_skill_count
                        best_duration = current_remap_duration
                        best_remap = remap_stats
    return best_remap              
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    