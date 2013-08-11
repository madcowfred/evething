EVEthing.skillplan = {
    // current skill popover displayed
    current_popover_id: false,
    
    skillplanId: 0,
    addSkillInPlanUrl: "",
    skillPlanEntriesURL: "",
    
    onload: function() {
        $('#apply_filter').click(function(){EVEthing.skillplan.reload_entries()});               
        
        // hover thing for skill descriptions
        $('.skill-list-hover').popover({ 
            animation: false, 
            trigger: 'click', 
            html: true,
            placement: 'left',
            container: 'body'
        }).on('click', 
            function() {
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
                
                return false;
            }
        );
        EVEthing.skillplan.reload_entries()
    },
    
    addRemapPoint: function() {
        return false;
    },
    
    addSkillInPlan: function(skill_id, level) {
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
                response = $.parseJSON(json);
                if(response.status == "ok"){
                    $('#'+EVEthing.skillplan.current_popover_id).popover('hide');
                    EVEthing.skillplan.reload_entries();
                }
            },
            error: function(xhr, status, error) {
                // display the error for the user (at least !)
            }
        });
    },
    
    reload_entries: function() {
        // call a page with a $.get to grab the skillplan entries.
        ajax_wait = true;

        var implants     = $('#implants').val();
        var character_id = Math.max($('#characters').val(), 0);
        var show_trained = ($('#show_trained').is(':checked')) ? 1 : 0;
        var url          = EVEthing.skillplan.skillPlanEntriesURL.replace('99999999999', EVEthing.skillplan.skillplanId)
                                                                 .replace('88888888888', character_id)
                                                                 .replace('77777777777', implants)
                                                                 .replace('66666666666', show_trained)
        
        $.get(url, function(data) {
            $('#skillplan').html(data); 
            
            
            // we need to reset the hover
            $('.skill-hover').popover({ animation: false, trigger: 'hover', html: true });
            $('#skillplan tbody').sortable({
                axis: "y",
                containment: "parent" ,
                cursor: "move",
                handle: ".skill_entry_handler",
                helper: "clone",
                start: function(event, ui) {
                },
                stop: function(event, ui) {
                }
            });
          //  $('#skillplan tbody').disableSelection();
        })

    },
    
    optimizeAttributes: function() {
    
    },
    
    optimizeRemaps: function() {
    
    },

}
