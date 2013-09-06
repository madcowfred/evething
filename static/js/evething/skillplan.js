EVEthing.skillplan = {
    // current skill popover displayed
    current_popover_id: false,
    
    skillplanId: 0,
    
    addSkillInPlanUrl: "",
    addRemapInPlanUrl: "",
    skillPlanEntriesEditUrl: "",
    reorderEntriesUrl: "",
    deleteEntryUrl: "",
    cleanSkillplanUrl: "",
    optimizeSkillplanUrl: "",
    optimizeSkillplanRemapsUrl = "",

    
    onload: function() {
        $('#apply_filter').on('click',
            function(e){
                EVEthing.skillplan.reloadEntries();
                e.preventDefault();
            }
        );        
        
        $('#add_remap').on('click',
            function(e) {
                EVEthing.skillplan.addRemapPoint();
                e.preventDefault();
            }
        );       
        
        $('#optimize_attr').on('click',
            function(e) {
                EVEthing.skillplan.optimizeAttributes();
                e.preventDefault();
            }
        );   
        
        $('#optimize_remap').on('click',
            function(e) {
                EVEthing.skillplan.optimizeRemaps();
                e.preventDefault();
            }
        );       
        
        $('#searchSkill').on('keyup',EVEthing.skillplan.searchSkill);
        $('#clean_skillplan').on('click',
            function(e) {
                var confirmDelete = confirm("Are you sure you want to remove all entries from this skillplan ?")
                if(confirmDelete) {
                    EVEthing.skillplan.cleanSkillPlan();
                }
                e.preventDefault();
            }
        );
        
        // hover thing for skill descriptions
        $('.skill-list-hover').popover({ 
            animation: false, 
            trigger: 'click', 
            html: true,
            placement: 'left',
            container: 'body'
        }).on('click', 
            function(e) {
            
                // popover on click, but only display one popover.
                if(EVEthing.skillplan.current_popover_id) {
                    if(EVEthing.skillplan.current_popover_id != $(this).attr('id')) {
                        $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    }
                }
                EVEthing.skillplan.current_popover_id=$(this).attr('id');
                
                // define click events on button in the popover        
                $('.btn-plan-skill').on('click',
                    function() {
                        var plan_to_level   = $(this).attr('data-level');
                        var plan_skill_id   = $(this).attr('data-id');
                        EVEthing.skillplan.addSkillInPlan(plan_skill_id, plan_to_level);
                        return false;
                    }
                );
                
                e.preventDefault();
            }
        );
        EVEthing.skillplan.reloadEntries()
    },
    
    reloadEntries: function() {
        // call a page with a $.get to grab the skillplan entries.
        
        var implants     = $('#implants').val();
        var character_id = Math.max($('#characters').val(), 0);
        var show_trained = ($('#show_trained').is(':checked')) ? 1 : 0;
        var url          = EVEthing.skillplan.skillPlanEntriesEditUrl.replace('99999999999', EVEthing.skillplan.skillplanId)
                                                                     .replace('88888888888', character_id)
                                                                     .replace('77777777777', implants)
                                                                     .replace('66666666666', show_trained)
        
        $.get(url, function(data) {
            $('#skillplan').html(data); 
            
            
            // we need to reset bindings in the loaded page
            $('.skill-hover').popover({ animation: false, trigger: 'hover', html: true });
            $('.tooltips').tooltip();
            
            // init the delete bind
            $('.remove-entry').on('click',
                function(e) {
                    var confirmDelete = confirm("Are you sure you want to delete this entry?\nNote: All entries depending on that skill will be deleted in the process.")
                    if(confirmDelete) {
                        EVEthing.skillplan.deleteEntry($(this).attr('data-id'));
                    }
                    e.preventDefault();
                }
            );
                        
            // create the sortable bind
            $('#skillplan tbody').sortable({
                axis: "y",
                containment: "#skillplan" ,
                cursor: "move",
                //handle: ".skill_entry_handler",
                helper: function(e, tr)
                {
                    var $originals = tr.children();
                    var $helper = tr.clone();
                    $helper.children().each(function(index)
                    {
                        // Set helper cell sizes to match the original sizes
                        $(this).width($originals.eq(index).width());
                    });
                    return $helper;
                },
                start: function(event, ui) {    
                    EVEthing.skillplan.previous_entries_number = ui.item.prevAll().length;
                },
                stop: function(event, ui) {
                    // if we have the same number of previous entries, it's like we didn't move the entry
                    if(ui.item.prevAll().length != EVEthing.skillplan.previous_entries_number) {
                                               
                        // what is the new position ?
                        var new_position = 0;
                        
                        if(ui.item.prev().length != 0) {
                            if(parseInt(ui.item.prev().attr('data-position')) < parseInt(ui.item.attr('data-position'))) {
                                new_position = ui.item.next().attr('data-position');
                            } else {
                                new_position = ui.item.prev().attr('data-position');
                            }
                        }
                        
                        EVEthing.skillplan.reorderEntry(ui.item.attr('data-id'), new_position);                    
                    }
                }
            });
        })
    },

    addRemapPoint: function() {
        if(EVEthing.skillplan.addRemapInPlanUrl == "") {
            alert('Add Remap URL is not set');
            return;
        }
        var data = { skillplan_id:EVEthing.skillplan.skillplanId };        
        EVEthing.skillplan.ajaxCall(EVEthing.skillplan.addRemapInPlanUrl, data); 
    },
    
    cleanSkillPlan: function() {
        if(EVEthing.skillplan.cleanSkillplanUrl == "") {
            alert('Clean SkillPlan URL is not set');
            return;
        }
        var data = { skillplan_id:EVEthing.skillplan.skillplanId };        
        EVEthing.skillplan.ajaxCall(EVEthing.skillplan.cleanSkillplanUrl, data); 
    },
    
    deleteEntry: function(entry_id) {
        if(EVEthing.skillplan.deleteEntryUrl == "") {
            alert('Delete entry URL is not set');
            return;
        }
        var data = { skillplan_id:EVEthing.skillplan.skillplanId
                   , entry_id:entry_id};        
        EVEthing.skillplan.ajaxCall(EVEthing.skillplan.deleteEntryUrl, data); 
    },
    
    addSkillInPlan: function(skill_id, level) {

        if(EVEthing.skillplan.addSkillInPlanUrl == "") {
            alert('Add Skill URL is not set');
            return;
        }
        
        // need to do the full ajax, since we need to manage the popover :(
        $.ajax({
            crossDomain: false,
            url: EVEthing.skillplan.addSkillInPlanUrl,
            data: { skill_id:skill_id
                  , skill_level:level
                  , skillplan_id:EVEthing.skillplan.skillplanId },
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                var response = $.parseJSON(json);
                if(response.status == "ok"){
                    $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    EVEthing.skillplan.reloadEntries();
                }
            },
            error: function(xhr, status, error) {
                alert("Error " + xhr.status + ": " +xhr.responseText)
            }
        });
    },
   
    reorderEntry: function(entry, new_position) {
        if(EVEthing.skillplan.reorderEntriesUrl == "") {
            alert('Reorder Skill URL is not set');
            return;
        }
        var data = { entry_id:entry
                   , new_position:new_position
                   , skillplan_id:EVEthing.skillplan.skillplanId };
                   
        EVEthing.skillplan.ajaxCall(EVEthing.skillplan.reorderEntriesUrl, data, true); 
    },
    
    optimizeAttributes: function() {
        alert('not working yet');
    },
    
    optimizeRemaps: function() {
        alert('not working yet');
    },

    ajaxCall: function(url, data, reloadIfError) {    
        reloadIfError = (typeof reloadIfError === 'undefined') ? false : reloadIfError;
        
        $.ajax({
            crossDomain: false,
            url: url,
            data: data,
            type:'post',
            beforeSend: function(xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
            },
            success: function(json) {
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    EVEthing.skillplan.reloadEntries();
                }
            },
            error: function(xhr, status, error) {
                alert("Error " + xhr.status + ": " +xhr.responseText)
                if(reloadIfError) {
                    EVEthing.skillplan.reloadEntries();
                }
            }
        });
    },
    
    searchSkill: function() {
        var text = $('#searchSkill').val().toLowerCase();
        $('#skill_list ul').each(
            function() {
                var found = false;
                $(this).css('display','none');
                var children = $(this).find('.nav-header').attr('data-target');
                
                $(this).find(children).each(
                    function() {
                        if($(this).attr('data-name').toLowerCase().indexOf(text) >= 0) {
                            found = true;
                            $(this).addClass('in').css('height','auto');
                        } else {
                            $(this).removeClass('in').css('height','0px');
                        }
                    }
                );
                
                
                if(found || text.length == 0) {
                    $(this).css('display','');
                    
                    if(text.length == 0) {
                        $(this).find(children).removeClass('in').css('height','0px');
                    }
                }
            }
        );
    },
    

}
